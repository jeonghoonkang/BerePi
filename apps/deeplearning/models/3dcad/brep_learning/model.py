"""A geometry encoder plus edge-aware face adjacency graph network."""

from __future__ import annotations

import torch
from torch import nn

from .features import EDGE_FEATURE_DIM, FACE_SCALAR_DIM, UV_CHANNELS


class FaceGeometryEncoder(nn.Module):
    def __init__(self, hidden_dim: int):
        super().__init__()
        self.grid = nn.Sequential(
            nn.Conv2d(UV_CHANNELS, 32, 3, padding=1), nn.BatchNorm2d(32), nn.SiLU(),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.SiLU(),
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
        )
        self.fuse = nn.Sequential(nn.Linear(64 + FACE_SCALAR_DIM, hidden_dim), nn.SiLU(),
                                  nn.LayerNorm(hidden_dim))

    def forward(self, uv: torch.Tensor, attr: torch.Tensor) -> torch.Tensor:
        return self.fuse(torch.cat((self.grid(uv), attr), dim=-1))


class EdgeMessageLayer(nn.Module):
    """Directed message passing conditioned on shared-edge geometry."""

    def __init__(self, hidden_dim: int, dropout: float):
        super().__init__()
        self.message = nn.Sequential(nn.Linear(hidden_dim * 2 + EDGE_FEATURE_DIM, hidden_dim),
                                     nn.SiLU(), nn.Dropout(dropout), nn.Linear(hidden_dim, hidden_dim))
        self.update = nn.GRUCell(hidden_dim, hidden_dim)
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor) -> torch.Tensor:
        if edge_index.shape[1] == 0:
            return x
        src, dst = edge_index
        messages = self.message(torch.cat((x[src], x[dst], edge_attr), dim=-1))
        aggregated = torch.zeros_like(x)
        aggregated.index_add_(0, dst, messages)
        degree = torch.zeros(x.shape[0], device=x.device, dtype=x.dtype)
        degree.index_add_(0, dst, torch.ones_like(dst, dtype=x.dtype))
        aggregated = aggregated / degree.clamp_min(1).unsqueeze(-1)
        return self.norm(x + self.update(aggregated, x))


class BrepGraphNetwork(nn.Module):
    def __init__(self, num_classes: int, hidden_dim: int = 128,
                 message_passing_steps: int = 4, dropout: float = 0.15):
        super().__init__()
        self.encoder = FaceGeometryEncoder(hidden_dim)
        self.layers = nn.ModuleList([EdgeMessageLayer(hidden_dim, dropout)
                                     for _ in range(message_passing_steps)])
        self.head = nn.Sequential(nn.Linear(hidden_dim * 2, hidden_dim), nn.SiLU(),
                                  nn.Dropout(dropout), nn.Linear(hidden_dim, num_classes))

    def forward(self, face_uv: torch.Tensor, face_attr: torch.Tensor,
                edge_index: torch.Tensor, edge_attr: torch.Tensor,
                batch: torch.Tensor) -> torch.Tensor:
        x = self.encoder(face_uv, face_attr)
        for layer in self.layers:
            x = layer(x, edge_index, edge_attr)
        graph_count = int(batch.max()) + 1
        summed = torch.zeros((graph_count, x.shape[1]), device=x.device, dtype=x.dtype)
        summed.index_add_(0, batch, x)
        counts = torch.bincount(batch, minlength=graph_count).to(x.dtype).unsqueeze(-1)
        mean = summed / counts.clamp_min(1)
        maximum = torch.stack([x[batch == i].max(dim=0).values for i in range(graph_count)])
        return self.head(torch.cat((mean, maximum), dim=-1))
