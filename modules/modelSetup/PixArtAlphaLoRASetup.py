from typing import Iterable

import torch
from torch.nn import Parameter

from modules.model.PixArtAlphaModel import PixArtAlphaModel
from modules.modelSetup.BasePixArtAlphaSetup import BasePixArtAlphaSetup
from modules.module.LoRAModule import LoRAModuleWrapper
from modules.util import create
from modules.util.TrainProgress import TrainProgress
from modules.util.config.TrainConfig import TrainConfig


class PixArtAlphaLoRASetup(BasePixArtAlphaSetup):
    def __init__(
            self,
            train_device: torch.device,
            temp_device: torch.device,
            debug_mode: bool,
    ):
        super(PixArtAlphaLoRASetup, self).__init__(
            train_device=train_device,
            temp_device=temp_device,
            debug_mode=debug_mode,
        )

    def create_parameters(
            self,
            model: PixArtAlphaModel,
            config: TrainConfig,
    ) -> Iterable[Parameter]:
        params = list()

        if config.train_text_encoder:
            params += list(model.text_encoder_lora.parameters())

        if config.train_prior:
            params += list(model.transformer_lora.parameters())

        return params

    def create_parameters_for_optimizer(
            self,
            model: PixArtAlphaModel,
            config: TrainConfig,
    ) -> Iterable[Parameter] | list[dict]:
        param_groups = list()

        if config.train_text_encoder:
            param_groups.append(
                self.create_param_groups(config, model.text_encoder_lora.parameters(), config.text_encoder_learning_rate)
            )

        if config.train_prior:
            param_groups.append(
                self.create_param_groups(config, model.transformer_lora.parameters(), config.prior_learning_rate)
            )

        return param_groups

    def setup_model(
            self,
            model: PixArtAlphaModel,
            config: TrainConfig,
    ):
        if model.text_encoder_lora is None and config.train_text_encoder:
            model.text_encoder_lora = LoRAModuleWrapper(
                model.text_encoder, config.lora_rank, "lora_te", config.lora_alpha
            )

        if model.transformer_lora is None and config.train_prior:
            model.transformer_lora = LoRAModuleWrapper(
                model.transformer, config.lora_rank, "lora_transformer", config.lora_alpha, ["attn1", "attn2"]
            )

        train_text_encoder = config.train_text_encoder and (model.train_progress.epoch < config.train_text_encoder_epochs)
        if model.text_encoder_lora is not None:
            model.text_encoder_lora.requires_grad_(train_text_encoder)

        train_prior = config.train_prior and (model.train_progress.epoch < config.train_prior_epochs)
        if model.transformer_lora is not None:
            model.transformer_lora.requires_grad_(train_prior)

        model.vae.requires_grad_(False)

        # if args.rescale_noise_scheduler_to_zero_terminal_snr:
        #     model.rescale_noise_scheduler_to_zero_terminal_snr()
        #     model.force_v_prediction()
        # elif args.force_v_prediction:
        #     model.force_v_prediction()
        # elif args.force_epsilon_prediction:
        #     model.force_epsilon_prediction()

        if model.text_encoder_lora is not None:
            model.text_encoder_lora.hook_to_module()
            model.text_encoder_lora.to(dtype=config.lora_weight_dtype.torch_dtype())
        if model.transformer_lora is not None:
            model.transformer_lora.hook_to_module()
            model.transformer_lora.to(dtype=config.lora_weight_dtype.torch_dtype())

        model.optimizer = create.create_optimizer(
            self.create_parameters_for_optimizer(model, config), model.optimizer_state_dict, config
        )
        del model.optimizer_state_dict

        model.ema = create.create_ema(
            self.create_parameters(model, config), model.ema_state_dict, config
        )
        del model.ema_state_dict

        self.setup_optimizations(model, config)

    def setup_train_device(
            self,
            model: PixArtAlphaModel,
            config: TrainConfig,
    ):
        vae_on_train_device = self.debug_mode or config.align_prop
        text_encoder_on_train_device = config.train_text_encoder or config.align_prop or not config.latent_caching

        model.text_encoder_to(self.train_device if text_encoder_on_train_device else self.temp_device)
        model.vae_to(self.train_device if vae_on_train_device else self.temp_device)
        model.transformer_to(self.train_device)

        if config.train_text_encoder:
            model.text_encoder.train()
        else:
            model.text_encoder.eval()

        model.vae.eval()

        if config.train_prior:
            model.transformer.train()
        else:
            model.transformer.eval()

    def after_optimizer_step(
            self,
            model: PixArtAlphaModel,
            config: TrainConfig,
            train_progress: TrainProgress
    ):
        train_text_encoder = config.train_text_encoder and (model.train_progress.epoch < config.train_text_encoder_epochs)
        model.text_encoder.requires_grad_(train_text_encoder)

        train_prior = config.train_prior and (model.train_progress.epoch < config.train_prior_epochs)
        model.transformer.requires_grad_(train_prior)
