import argparse
from builtins import eval
from typing import Optional

from hydra import compose, initialize_config_dir
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

OmegaConf.register_new_resolver("eval", eval)


def parse_config_overrides(config_overrides: Optional[str]) -> Optional[list]:
    if config_overrides is None:
        return None

    parser = argparse.ArgumentParser()
    parser.add_argument("overrides", nargs="*")

    args = parser.parse_args(config_overrides.split())

    return args.overrides


def load_hydra_config(
    config_dir: str,
    config_name: str = "config",
    return_hydra_section: bool = True,
    config_overrides: Optional[str] = None,
) -> DictConfig:
    overrides = parse_config_overrides(config_overrides)

    with initialize_config_dir(config_dir=config_dir, version_base="1.1"):
        kwargs = dict(config_name=config_name, return_hydra_config=return_hydra_section)
        if overrides is not None:
            kwargs["overrides"] = overrides

        config: DictConfig = compose(**kwargs)

    HydraConfig().cfg = config
    OmegaConf.resolve(config)

    config: DictConfig = OmegaConf.to_container(config, resolve=True)

    return config