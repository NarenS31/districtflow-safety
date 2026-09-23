"""DistrictFlow RiskGNN — a spatial GNN for per-segment pedestrian/cyclist risk.

PROVENANCE: this is a direct architectural fork of XTraffic's XTrafficSTGNN
(OlympiFlow repo, models/gnn/stgnn.py). Per the project brief, we reuse the
GRAPH CONVOLUTION core and the MOD-1 learned-adjacency-blend idea, and we
explicitly DO NOT reuse the METR-LA/PEMS-BAY forecasting task head. We also
drop XTraffic's MOD-2 (multi-scale dilated TEMPORAL convolution) entirely —
documented below, this is a real architectural decision, not an oversight.

WHAT CARRIES OVER FROM XTRAFFIC, UNCHANGED IN SPIRIT:
  - GraphConv: order-K diffusion graph convolution over one or more [N,N]
    supports (XTraffic's exact mechanism — A^1 x, A^2 x, ... concatenated and
    mixed by a 1x1 conv). Spatial message passing doesn't depend on the task
    being a forecast, so this ports with no change to the math, only to the
    tensor rank (see below).
  - MOD 1, semantic + adaptive adjacency blend: a learned co-movement-style
    graph blended with the physical (shared-intersection) graph via a
    learnable sigmoid scalar, PLUS a second purely-adaptive graph from node
    embeddings. XTraffic used this to let the model discover roads that
    behave alike beyond physical adjacency (e.g. two disconnected commercial
    strips with similar traffic patterns); here it lets the model discover
    road SEGMENTS with similar risk profiles beyond physical adjacency (e.g.
    two arterial stretches through similar rural terrain in different
    counties). Same mechanism, same justification, different domain.
  - MOD 3, HeteroFusion: per-modality encoder + learnable gate, missing
    modality -> zeroed contribution, never a crash. XTraffic needed this
    because Chicago lacked some of LA's modalities (weather/events/transit).
    We need it for exactly the same reason, sharper: NC-08's rural counties
    (Anson, Richmond, Montgomery, Stanly) have sparser crash/incident records
    than Mecklenburg's Charlotte suburbs, and per-county EMS station data may
    be incomplete. A segment with a missing modality must still get a score,
    with that gap surfaced as low confidence — not silently zero-filled and
    presented as equally precise. See docs/LIMITATIONS.md.

WHAT DOES NOT CARRY OVER (flagged, not silent):
  - MOD 2 (multi-scale dilated temporal conv) is DROPPED. XTraffic forecasts
    a future speed from a 12-step (1-hour) sliding window of sensor readings
    — a genuine time series. Our inputs are AADT (an ANNUAL average, not a
    time series — the brief is explicit this must never be treated as one)
    and 5-YEAR crash/incident COUNTS. There is no sub-annual temporal signal
    to convolve over. A model with a temporal-conv stack bolted onto static
    inputs would either be a no-op (T=1) or would fabricate temporal
    structure that isn't in the data — so we build a purely SPATIAL stack:
    stacked GraphConv blocks with residual connections, no time axis at all.
  - Tensor rank: XTraffic tensors are [B, C, N, T] (batch, channels, nodes,
    time) because Conv2d needs a 2-D spatial grid to convolve over (node, T).
    We have no batch dimension either — NC-08 is ONE graph, and training is
    transductive node regression over its segments (the standard setting for
    graph node tasks, e.g. citation-network node classification), not
    supervised learning over many independent graphs. So tensors here are
    [N, C] (segments, channels) and GraphConv's einsum drops the batch/time
    axes accordingly. The diffusion math (A^k x) is otherwise identical.

TASK HEAD: XTraffic predicts z-scored future speed (regression against a
held-out ground truth speed). We predict a continuous RISK SCORE per segment,
supervised by the ped/cyclist incident + crash history (see
models/risk/targets.py for how that target is built and configs/model.yaml
for the loss choice). This file only defines the architecture + forward pass;
loss/training live in train.py, matching the XTraffic file-split convention
(architecture vs. training vs. evaluation as separate files).

Python 3.9 compatible (typing.Optional/Dict, no `X | Y`).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# MOD 3 — Heterogeneous feature fusion (static, per-segment; T axis removed)
# ---------------------------------------------------------------------------
class HeteroFusion(nn.Module):
    """Encode each feature modality separately, sum with learnable gates.

    Ported from XTraffic's HeteroFusion. There, a "modality" was a whole
    sensory channel (weather/events/transit) attached to a [B,C,N,T] tensor
    and encoded with a 1x1 Conv2d. Here a "modality" is a group of related
    per-segment features (see docs/FEATURES.md for the exact grouping —
    infrastructure, crash_history, ems_access, context), each a [N, C_name]
    matrix, encoded with a plain Linear layer (the T and B axes XTraffic's
    Conv2d convolved over don't exist here, so a 1x1 conv over [N,C] IS a
    per-node linear layer — Linear is the same operation with less machinery).

    A modality absent for a segment (e.g. no EMS routing data for an isolated
    rural intersection) is passed as None for the WHOLE batch it's missing
    from; per-segment (row-level) missingness is instead handled by a mask
    that zeros the row before this module ever sees it (built in
    data/pipelines feature assembly) so a partially-missing modality doesn't
    need per-row branching here — same "don't crash on missing data" goal as
    XTraffic, implemented at the data layer for row-level gaps and at this
    module for whole-modality gaps.
    """

    def __init__(self, modality_dims: Dict[str, int], out_channels: int):
        super().__init__()
        self.encoders = nn.ModuleDict(
            {name: nn.Linear(dim, out_channels) for name, dim in modality_dims.items()}
        )
        # Init at 0 -> sigmoid(0)=0.5, neutral gate the model pushes toward
        # 0 (ignore this modality) or 1 (rely on it) during training.
        self.gate_logits = nn.ParameterDict(
            {name: nn.Parameter(torch.zeros(1)) for name in modality_dims}
        )

    def forward(self, modalities: Dict[str, Optional[torch.Tensor]]) -> torch.Tensor:
        # modalities[name] : [N, C_name]  or None if that feed is absent
        # network-wide (e.g. no AADT service at all, vs. a per-segment gap).
        fused = None  # -> [N, out_channels]
        for name, encoder in self.encoders.items():
            x = modalities.get(name, None)
            if x is None:
                continue
            gate = torch.sigmoid(self.gate_logits[name])   # scalar in (0,1)
            enc = encoder(x) * gate                          # [N, out_channels]
            fused = enc if fused is None else fused + enc
        if fused is None:
            raise ValueError("HeteroFusion received no present modalities.")
        return fused  # [N, out_channels]

    def gate_values(self) -> Dict[str, float]:
        return {name: float(torch.sigmoid(p).item())
                for name, p in self.gate_logits.items()}


# ---------------------------------------------------------------------------
# Graph convolution (diffusion) over a set of support matrices — unchanged
# math from XTraffic, [N,C] instead of [B,C,N,T]
# ---------------------------------------------------------------------------
class GraphConv(nn.Module):
    """Order-K diffusion graph convolution over one or more [N, N] supports.

    Identical mechanism to XTraffic's GraphConv: for each support A, form
    A^1 x, A^2 x, ..., A^order x (risk-relevant "influence" diffusing 1..order
    hops across shared intersections), concatenate with the input, mix with a
    linear layer. Only the tensor rank changed (no batch/time axes).
    """

    def __init__(self, in_channels: int, out_channels: int,
                 n_supports: int, order: int = 2, dropout: float = 0.3):
        super().__init__()
        self.order = order
        self.dropout = dropout
        mix_in = in_channels * (1 + order * n_supports)
        self.mix = nn.Linear(mix_in, out_channels)

    @staticmethod
    def _diffuse(x: torch.Tensor, A: torch.Tensor) -> torch.Tensor:
        # x:[N,C], A:[N,N] -> [N,C]. One hop of message passing: each segment
        # picks up a weighted average of its graph-neighbors' features.
        return A @ x

    def forward(self, x: torch.Tensor, supports: List[torch.Tensor]) -> torch.Tensor:
        out = [x]                        # 0-hop (self) term
        for A in supports:
            xk = x
            for _ in range(self.order):
                xk = self._diffuse(xk, A)
                out.append(xk)
        h = torch.cat(out, dim=-1)       # [N, C*(1+order*n_supports)]
        h = self.mix(h)                  # [N, out_channels]
        h = F.dropout(h, self.dropout, training=self.training)
        return h


# ---------------------------------------------------------------------------
# One spatial residual block (XTraffic's STBlock with the temporal-conv half
# removed — MOD 2 does not apply here, see module docstring)
# ---------------------------------------------------------------------------
class SpatialBlock(nn.Module):
    def __init__(self, hidden_channels: int, n_supports: int,
                 gcn_order: int, dropout: float):
        super().__init__()
        self.gconv = GraphConv(hidden_channels, hidden_channels, n_supports,
                                order=gcn_order, dropout=dropout)
        self.bn = nn.BatchNorm1d(hidden_channels)

    def forward(self, x: torch.Tensor, supports: List[torch.Tensor]) -> torch.Tensor:
        residual = x
        h = F.relu(self.gconv(x, supports))
        h = h + residual
        h = self.bn(h)
        return h


# ---------------------------------------------------------------------------
# The full model
# ---------------------------------------------------------------------------
class RiskGNN(nn.Module):
    """Spatial GNN producing a continuous risk score per road segment.

    forward() accepts a modality dict of [N, C_name] tensors and the segment
    adjacency, and returns raw risk logits [N] (pass through softplus outside
    the model for a non-negative rate, or use directly with a Poisson/NB loss
    — see train.py; keeping the head's final nonlinearity out of the module
    matches XTraffic's convention of returning z-scored values and letting
    the caller invert/transform, so the loss function owns that choice).
    """

    def __init__(self, num_segments: int, physical_adj: torch.Tensor,
                 modality_dims: Dict[str, int],
                 hidden_channels: int = 32, n_blocks: int = 4,
                 embed_dim: int = 10, gcn_order: int = 2, dropout: float = 0.3,
                 use_semantic: bool = True):
        super().__init__()
        self.num_segments = num_segments
        self.use_semantic = use_semantic

        A = physical_adj.clone().float()
        A = A + torch.eye(num_segments)
        A = A / A.sum(dim=1, keepdim=True).clamp(min=1e-6)  # row-normalized
        self.register_buffer("physical_adj", A)             # [N, N]

        self.fusion = HeteroFusion(modality_dims, hidden_channels)

        # MOD 1: learned semantic co-movement-style graph, blended with the
        # physical (shared-intersection) graph via a learnable sigmoid alpha.
        self.sem_embed = nn.Parameter(torch.randn(num_segments, embed_dim) * 0.01)
        self.alpha_logit = nn.Parameter(torch.zeros(1))

        # Second, purely adaptive graph (XTraffic's Graph WaveNet inheritance).
        self.nodevec1 = nn.Parameter(torch.randn(num_segments, embed_dim) * 0.01)
        self.nodevec2 = nn.Parameter(torch.randn(num_segments, embed_dim) * 0.01)

        n_supports = 2  # [A_final (phys+semantic), A_adaptive]
        self.blocks = nn.ModuleList([
            SpatialBlock(hidden_channels, n_supports, gcn_order, dropout)
            for _ in range(n_blocks)
        ])

        self.readout = nn.Sequential(
            nn.Linear(hidden_channels, hidden_channels),
            nn.ReLU(),
            nn.Linear(hidden_channels, 1),
        )

    def _semantic_support(self) -> torch.Tensor:
        if not self.use_semantic:
            return self.physical_adj
        A_sem = F.softmax(F.relu(self.sem_embed @ self.sem_embed.t()), dim=1)
        a = torch.sigmoid(self.alpha_logit)
        return a * self.physical_adj + (1.0 - a) * A_sem

    def _adaptive_support(self) -> torch.Tensor:
        return F.softmax(F.relu(self.nodevec1 @ self.nodevec2.t()), dim=1)

    def current_alpha(self) -> float:
        return float(torch.sigmoid(self.alpha_logit).item())

    def forward(self, modalities: Dict[str, Optional[torch.Tensor]]) -> torch.Tensor:
        x = self.fusion(modalities)                       # [N, hidden]
        supports = [self._semantic_support(), self._adaptive_support()]
        for block in self.blocks:
            x = block(x, supports)                         # [N, hidden]
        out = self.readout(x).squeeze(-1)                  # [N]
        return out
