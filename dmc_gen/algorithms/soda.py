from copy import deepcopy

import torch
import torch.nn.functional as F

from dmc_gen.algorithms import modules as m
from dmc_gen.algorithms.sac import SAC
from dmc_gen.algorithms import augmentations
from dmc_gen import utils


class SODA(SAC):
    def __init__(self, obs_shape, action_shape, args):
        super().__init__(obs_shape, action_shape, args)
        self.aux_update_freq = args.aux_update_freq
        self.soda_batch_size = args.soda_batch_size
        self.soda_tau = args.soda_tau

        shared_cnn = self.critic.encoder.shared_cnn
        aux_cnn = self.critic.encoder.head_cnn
        soda_encoder = m.Encoder(
            shared_cnn,
            aux_cnn,
            m.SODAMLP(aux_cnn.out_shape[0], args.projection_dim, args.projection_dim)
        )

        self.predictor = m.SODAPredictor(soda_encoder, args.projection_dim).to(self.device)
        self.predictor_target = deepcopy(self.predictor)

        self.soda_optimizer = torch.optim.Adam(
            self.predictor.parameters(), lr=args.aux_lr, betas=(args.aux_beta, 0.999)
        )
        self.train()

    def train(self, training=True):
        super().train(training)
        if hasattr(self, 'soda_predictor'):
            self.soda_predictor.train(training)

    def compute_soda_loss(self, x0, x1):
        h0 = self.predictor(x0)
        with torch.no_grad():
            h1 = self.predictor_target.encoder(x1)
        h0 = F.normalize(h0, p=2, dim=1)
        h1 = F.normalize(h1, p=2, dim=1)

        return F.mse_loss(h0, h1)

    def update_soda(self, replay_buffer):
        from ml_logger import logger
        x = replay_buffer.sample_soda(self.soda_batch_size)
        assert x.size(-1) == 100

        aug_x = x.clone()

        x = augmentations.random_crop(x)
        aug_x = augmentations.random_crop(aug_x)
        aug_x = augmentations.random_overlay(aug_x)

        soda_loss = self.compute_soda_loss(aug_x, x)

        self.soda_optimizer.zero_grad()
        soda_loss.backward()
        self.soda_optimizer.step()
        logger.store_metrics({'soda/loss': soda_loss})

        utils.soft_update_params(
            self.predictor, self.predictor_target,
            self.soda_tau
        )

    def update(self, replay_buffer, step):
        obs, action, reward, next_obs, not_done = replay_buffer.sample()

        self.update_critic(obs, action, reward, next_obs, not_done)

        if step % self.actor_update_freq == 0:
            self.update_actor_and_alpha(obs)

        if step % self.critic_target_update_freq == 0:
            self.soft_update_critic_target()

        if step % self.aux_update_freq == 0:
            self.update_soda(replay_buffer)
