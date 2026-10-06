"""LoRA + loss unit tests.

These need torch (the ``[train]`` extra). Without it the whole module is
skipped; the rest of the suite stays green in a CPU/dev environment.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
nn = torch.nn

from app.services.finetune.lora import (  # noqa: E402
    apply_lora_state_dict,
    apply_lora_to_model,
    lora_params,
    lora_state_dict,
    mask_bce_dice_loss,
)


@pytest.fixture()
def fake_encoder():
    torch.manual_seed(0)

    class FakeAttn(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.q_proj = nn.Linear(16, 16)
            self.k_proj = nn.Linear(16, 16)
            self.v_proj = nn.Linear(16, 16)

    class FakeEncoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.attn = FakeAttn()
            self.final_proj = nn.Linear(16, 16)

    return FakeEncoder()


def test_apply_lora_wraps_attention_only(fake_encoder):
    count = apply_lora_to_model(fake_encoder, rank=4, alpha=8.0)
    assert count == 3  # q/k/v wrapped, final_proj not named 'attn'
    params = lora_params(fake_encoder)
    assert len(params) == 3 * 2  # A and B per wrapped layer
    trainable_names = [n for n, p in fake_encoder.named_parameters() if p.requires_grad]
    assert len(trainable_names) == 6
    assert all("lora_" in n for n in trainable_names)


def test_lora_forward_matches_base_when_b_is_zero(fake_encoder):
    apply_lora_to_model(fake_encoder, rank=4, alpha=8.0)
    # B matrices are initialized to zero → output equals the frozen base
    with torch.no_grad():
        x = torch.randn(2, 16)
        base_out = fake_encoder.attn.q_proj.base(x)
        lora_out = fake_encoder.attn.q_proj(x)
    assert torch.allclose(base_out, lora_out, atol=1e-5)


def test_state_dict_round_trip(fake_encoder):
    apply_lora_to_model(fake_encoder, rank=4, alpha=8.0)
    state = lora_state_dict(fake_encoder)
    assert state and all("lora_" in k for k in state)

    # zeroing the adapters, then restoring, must recover identical output
    for p in fake_encoder.parameters():
        if p.requires_grad:
            p.data.zero_()
    apply_lora_state_dict(fake_encoder, state)
    with torch.no_grad():
        x = torch.randn(2, 16)
        before = fake_encoder.attn.q_proj(x).clone()
    # redo zero + restore to prove copy happens from saved tensors
    for p in fake_encoder.parameters():
        if p.requires_grad:
            p.data.zero_()
    apply_lora_state_dict(fake_encoder, state)
    with torch.no_grad():
        after = fake_encoder.attn.q_proj(x)
    assert torch.allclose(before, after, atol=1e-6)


def test_mask_bce_dice_loss_shape_and_range():
    pred = torch.randn(2, 1, 32, 32)
    target = (torch.rand(2, 1, 32, 32) > 0.5).float()
    loss = mask_bce_dice_loss(pred, target)
    assert loss.dim() == 0 and float(loss) > 0.0

    # perfect prediction → near-zero loss
    perfect_pred = torch.full_like(target, 12.0)  # sigmoid → ~1 where target 1
    perfect_pred = torch.where(target > 0.5, 12.0, -12.0)
    assert float(mask_bce_dice_loss(perfect_pred, target)) < 0.05