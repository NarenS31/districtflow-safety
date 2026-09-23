"""Layer 2 — per-segment feature-attribution explainer for RiskGNN.

PROVENANCE: a direct methodological fork of XTraffic's GNNExplainer
reimplementation (models/explainer/explain.py in the OlympiFlow repo). Same
optimization recipe from Ying et al. (NeurIPS 2019) — learn a small soft mask,
push it to preserve the prediction while staying small and near-binary:

    min_M   L(f(x), f(x ⊙ σ(M)))  +  λ_size·mean(σ(M))  +  λ_ent·H(σ(M))

WHAT'S DIFFERENT FROM XTRAFFIC (flagged, not silent): XTraffic masks OTHER
NODES (which sensors influenced this forecast — a spatial-propagation
question) and reports node/edge importance + a BFS path + a cross-correlation
lag. We mask the TARGET SEGMENT'S OWN INPUT FEATURES (which of ITS features —
AADT, crash history, EMS distance, rural flag, etc. — drove ITS score, a
feature-attribution question, per the brief). Concretely: every OTHER
segment's features stay fully present during masking (so the GNN's message
passing from neighbors is untouched and its influence is implicitly captured
in the "preserve the prediction" loss term), while only the target segment's
own feature row is multiplied by the learned mask. There is no edge mask, no
propagation path, and no lag — none of those exist for a static feature
vector. Same frozen-model, mask-only-optimization discipline as XTraffic.

Python 3.9 compatible. Shapes annotated where they change.
"""
from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from .schema import validate_explanation
from ..gnn.risk_gnn import RiskGNN


def _entropy(p: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    p = p.clamp(eps, 1 - eps)
    return -(p * torch.log(p) + (1 - p) * torch.log(1 - p))


class FeatureExplainer:
    """Learns a per-feature mask over ONE segment's own input, explaining why
    the frozen RiskGNN scored it the way it did.

    The model is FROZEN: only the mask tensor is optimized, never the network
    weights — we're asking what in this segment's input drove a fixed
    function's output, not retraining anything.
    """

    def __init__(self, model: RiskGNN, modalities: Dict[str, torch.Tensor],
                 device: torch.device, epochs: int = 200, lr: float = 0.05,
                 lambda_size: float = 0.15, lambda_ent: float = 0.05):
        self.model = model
        self.modalities = {k: v.to(device) for k, v in modalities.items()}
        self.device = device
        self.epochs = epochs
        self.lr = lr
        self.lambda_size = lambda_size
        self.lambda_ent = lambda_ent
        # Fixed order of (modality, channel) pairs -> one flat mask vector.
        # This ordering is reused everywhere a flat mask is unpacked/reported.
        self.layout: List[Tuple[str, int]] = []
        for name, x in self.modalities.items():
            for c in range(x.shape[1]):
                self.layout.append((name, c))

    def _forward_masked(self, target_idx: int, mask_logit: torch.Tensor) -> torch.Tensor:
        mask = torch.sigmoid(mask_logit)  # [n_features] in (0,1)
        masked: Dict[str, torch.Tensor] = {}
        offset = 0
        # Row selector is plain data (no autograd history), built once and
        # reused per modality — NOT an in-place write into `x` or `mask`
        # (that was the original bug: `xm[target_idx] = xm[target_idx] *
        # row_mask` overwrites the exact memory autograd needs to read on the
        # backward pass through the multiply, since LHS and RHS alias the
        # same storage — "modified by an inplace operation" is PyTorch
        # catching precisely that). `torch.where` below builds the masked
        # tensor OUT OF PLACE instead, so nothing needed for backward is ever
        # overwritten.
        is_target = (torch.arange(next(iter(self.modalities.values())).shape[0],
                                  device=self.device) == target_idx).unsqueeze(1)  # [N,1] bool
        for name, x in self.modalities.items():
            c = x.shape[1]
            row_mask = mask[offset:offset + c]              # [c]
            offset += c
            # Every segment other than target_idx keeps multiplier 1.0
            # (unchanged); the target segment's row is scaled by row_mask.
            multiplier = torch.where(is_target, row_mask.unsqueeze(0).expand(x.shape[0], -1),
                                     torch.ones_like(x))
            masked[name] = x * multiplier
        out = self.model(masked)                            # [N]
        return out[target_idx]

    def explain_target(self, target_idx: int, seed: int = 0
                       ) -> Tuple[np.ndarray, float]:
        """Returns (feature_importance[n_features] in [0,1], pred_orig_rate).

        pred_orig_rate is softplus(raw model output) — the same non-negative
        RATE transform models/gnn/evaluate.py applies to produce `risk_score`
        everywhere else in the pipeline, so an explanation's reported score
        always matches the dashboard's. The mask-preservation loss below
        optimizes in the model's RAW output space (pre-softplus) — that's an
        internal optimization detail and doesn't need to match the reported
        units, only be internally consistent, which it is (both sides of the
        loss are raw).
        """
        torch.manual_seed(seed)
        n_features = len(self.layout)

        with torch.no_grad():
            pred_orig_raw = self.model(self.modalities)[target_idx]
        pred_orig_val = float(pred_orig_raw.item())

        mask_logit = torch.randn(n_features, device=self.device) * 0.1
        mask_logit.requires_grad_(True)
        opt = torch.optim.Adam([mask_logit], lr=self.lr)

        for _ in range(self.epochs):
            opt.zero_grad()
            pred_masked = self._forward_masked(target_idx, mask_logit)
            loss = (pred_masked - pred_orig_val) ** 2
            m = torch.sigmoid(mask_logit)
            loss = loss + self.lambda_size * m.mean()
            loss = loss + self.lambda_ent * _entropy(m).mean()
            loss.backward()
            opt.step()

        importance = torch.sigmoid(mask_logit).detach().cpu().numpy()
        pred_orig_rate = float(torch.nn.functional.softplus(pred_orig_raw).item())
        return importance, pred_orig_rate


class ExplanationBuilder:
    """High-level: run the explainer, emit a schema-valid explanation dict."""

    def __init__(self, model: RiskGNN, modalities: Dict[str, torch.Tensor],
                 feature_names: Dict[str, List[str]], segment_meta: List[Dict],
                 checkpoint_path: str, district: str = "NC-08",
                 device: Optional[torch.device] = None,
                 top_k: int = 6, epochs: int = 200, confidence_runs: int = 5):
        self.model = model.to(device or torch.device("cpu"))
        self.model.eval()
        self.device = device or torch.device("cpu")
        self.modalities = modalities
        self.feature_names = feature_names
        self.segment_meta = segment_meta  # list of dicts, one per segment index
        self.checkpoint_path = checkpoint_path
        self.district = district
        self.top_k = top_k
        self.confidence_runs = confidence_runs
        self.explainer = FeatureExplainer(self.model, modalities, self.device,
                                          epochs=epochs)
        self.checkpoint_sha256 = self._checkpoint_hash(checkpoint_path)

    @staticmethod
    def _checkpoint_hash(path: str) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def _feature_name(self, layout_entry: Tuple[str, int]) -> str:
        name, c = layout_entry
        names = self.feature_names.get(name, [])
        return names[c] if c < len(names) else f"{name}[{c}]"

    def explain_segment(self, target_idx: int, timestamp: str) -> Dict:
        importance, pred_orig = self.explainer.explain_target(target_idx, seed=0)
        order = np.argsort(-importance)[: self.top_k]

        top_features = []
        for i in order:
            name, c = self.explainer.layout[i]
            value = float(self.modalities[name][target_idx, c].item())
            top_features.append({
                "feature_name": self._feature_name((name, c)),
                "importance": round(float(importance[i]), 4),
                "value": round(value, 4),
                "modality": name,
            })

        confidence = self._confidence(target_idx, order)

        meta_seg = self.segment_meta[target_idx]
        meta = {
            "district": self.district,
            "timestamp": timestamp,
            "model_checkpoint": os.path.basename(self.checkpoint_path),
        }
        if self.checkpoint_sha256:
            meta["model_checkpoint_sha256"] = self.checkpoint_sha256

        exp = {
            "meta": meta,
            "segment": {
                "segment_id": str(meta_seg["segment_id"]),
                "segment_name": str(meta_seg.get("segment_name", meta_seg["segment_id"])),
                "county": str(meta_seg.get("county", "unknown")),
                "rural_flag": bool(meta_seg.get("rural_flag", False)),
                "risk_score": round(pred_orig, 4),
                "risk_exposure_score": round(float(meta_seg.get("risk_exposure_score", pred_orig)), 4),
            },
            "top_features": top_features,
            "data_density_flag": bool(meta_seg.get("data_density_flag", False)),
            "explanation_confidence": round(float(confidence), 4),
        }
        problems = validate_explanation(exp)
        if problems:
            print("[explainer] WARNING schema problems:", problems)
        return exp

    def _confidence(self, target_idx: int, base_order: np.ndarray) -> float:
        """Mean Jaccard similarity of the top-k feature SET across
        confidence_runs reruns with different mask-init seeds — same
        stability-under-reinit notion as XTraffic's explanation_confidence,
        applied to features instead of nodes."""
        base = set(base_order.tolist())
        if not base:
            return 0.0
        sims = []
        for k in range(1, self.confidence_runs + 1):
            importance, _ = self.explainer.explain_target(target_idx, seed=k)
            other = set(np.argsort(-importance)[: self.top_k].tolist())
            union = base | other
            sims.append(len(base & other) / len(union) if union else 0.0)
        return float(np.mean(sims)) if sims else 0.0
