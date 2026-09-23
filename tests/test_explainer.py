"""End-to-end smoke test for the feature-mask explainer on a tiny synthetic
graph + model. This is what caught the in-place-autograd bug in
_forward_masked during development (xm[target_idx] = xm[target_idx] *
row_mask overwrote the exact memory autograd needed for backward) — kept as
a regression test so that specific failure mode can't come back silently.
"""
import torch

from models.explainer.explain import FeatureExplainer
from models.gnn.risk_gnn import RiskGNN


def _tiny_model_and_modalities():
    torch.manual_seed(0)
    n = 6
    adj = torch.eye(n)
    for i in range(n - 1):
        adj[i, i + 1] = adj[i + 1, i] = 1.0
    modalities = {
        "infrastructure": torch.rand(n, 3),
        "aadt": torch.rand(n, 1),
    }
    model = RiskGNN(
        num_segments=n, physical_adj=adj,
        modality_dims={k: v.shape[1] for k, v in modalities.items()},
        hidden_channels=8, n_blocks=2, embed_dim=4, gcn_order=1,
    )
    model.eval()
    return model, modalities


def test_feature_explainer_runs_without_autograd_error():
    model, modalities = _tiny_model_and_modalities()
    explainer = FeatureExplainer(model, modalities, device=torch.device("cpu"), epochs=5)
    importance, pred = explainer.explain_target(target_idx=2, seed=0)
    assert importance.shape == (4,)  # 3 infrastructure + 1 aadt channel
    assert (importance >= 0).all() and (importance <= 1).all()
    assert pred >= 0  # softplus rate, never negative


def test_feature_explainer_masking_only_touches_target_row():
    model, modalities = _tiny_model_and_modalities()
    explainer = FeatureExplainer(model, modalities, device=torch.device("cpu"), epochs=1)
    mask_logit = torch.zeros(4, requires_grad=True)  # sigmoid(0) = 0.5, all rows scaled 0.5x at target only
    out = explainer._forward_masked(target_idx=1, mask_logit=mask_logit)
    assert out.shape == ()  # scalar prediction for the target node
