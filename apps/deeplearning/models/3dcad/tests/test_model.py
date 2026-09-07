import torch

from brep_learning.features import EDGE_FEATURE_DIM, FACE_SCALAR_DIM, UV_CHANNELS
from brep_learning.model import BrepGraphNetwork


def test_forward_and_backward_on_variable_graph_batch():
    # Two solids containing 3 and 2 faces. Edges are stored in both directions.
    face_count, resolution = 5, 8
    edge_index = torch.tensor([[0, 1, 1, 2, 3, 4], [1, 0, 2, 1, 4, 3]])
    model = BrepGraphNetwork(num_classes=4, hidden_dim=32, message_passing_steps=2)
    logits = model(
        torch.randn(face_count, UV_CHANNELS, resolution, resolution),
        torch.randn(face_count, FACE_SCALAR_DIM), edge_index,
        torch.randn(edge_index.shape[1], EDGE_FEATURE_DIM),
        torch.tensor([0, 0, 0, 1, 1]),
    )
    assert logits.shape == (2, 4)
    logits.sum().backward()
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_isolated_face_is_supported():
    model = BrepGraphNetwork(num_classes=2, hidden_dim=16, message_passing_steps=1)
    output = model(torch.randn(1, UV_CHANNELS, 6, 6), torch.randn(1, FACE_SCALAR_DIM),
                   torch.empty(2, 0, dtype=torch.long), torch.empty(0, EDGE_FEATURE_DIM),
                   torch.zeros(1, dtype=torch.long))
    assert output.shape == (1, 2)
