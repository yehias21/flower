"""Client for FedPara."""
from typing import Optional
from collections import OrderedDict
from typing import Callable, Dict, List, Tuple
import flwr as fl
import torch
from flwr.common import NDArrays, Scalar
from hydra.utils import instantiate
from omegaconf import DictConfig
from torch.utils.data import DataLoader
from fedpara.models import train
import copy

class FedParaClient(fl.client.NumPyClient):
    """Standard Flower client for CNN training."""

    def __init__(
        self,
        cid: int,
        net: torch.nn.Module,
        train_loader: DataLoader,
        device: str,
        num_epochs: int,
    ):  # pylint: disable=too-many-arguments
        print(f"Initializing Client {cid}")
        self.cid = cid
        self.net = net
        self.train_loader = train_loader
        self.device = torch.device(device)
        self.num_epochs = num_epochs        
    def get_parameters(self, config: Dict[str, Scalar]) -> NDArrays:
        """Return the parameters of the current net."""
        return [val.cpu().numpy() for _, val in self.net.state_dict().items()]
        
    def _set_parameters(self, parameters: NDArrays) -> None:
        params_dict = zip(self.net.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
        self.net.load_state_dict(state_dict, strict=True)
            
    def fit(
        self, parameters: NDArrays, config: Dict[str, Scalar]
    ) -> Tuple[NDArrays, int, Dict]:
        """Train the network on the training set."""
        self._set_parameters(parameters)
        print(f"Client {self.cid} Training...")

        train(
            self.net,
            self.train_loader,
            self.device,
            epochs=self.num_epochs,
            hyperparams=config,
            round=config["curr_round"],
        )

        return (
            self.get_parameters({}),
            len(self.train_loader),
            {},
        )


class PFedParaClient(fl.client.NumPyClient):
    """personalized FedPara Client"""
    def __init__(
        self,
        cid: int,
        net: torch.nn.Module,
        train_loader: DataLoader,
        test_dataset: List[DataLoader],
        device: str,
        num_epochs: int,
        state_path: str,
    ): 
        
        self.cid = cid
        self.net = net
        self.train_loader = train_loader
        self.test_dataset = test_dataset
        self.device = torch.device(device)
        self.num_epochs = num_epochs
        self.state_path = state_path
    
    def get_parameters(self, config: Dict[str, Scalar]) -> NDArrays:
        """Return the parameters of the current net."""
        return [val.cpu().numpy() for _, val in self.net.state_dict().items()]
        
    def _set_parameters(self, parameters: NDArrays) -> None:
        params_dict = zip(self.net.state_dict().keys(), parameters)
        state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
        self.net.load_state_dict(state_dict, strict=True)
            
    def fit(
        self, parameters: NDArrays, config: Dict[str, Scalar]
    ) -> Tuple[NDArrays, int, Dict]:
        """Train the network on the training set."""
        self._set_parameters(parameters)
        print(f"Client {self.cid} Training...")

        train(
            self.net,
            self.train_loader,
            self.device,
            epochs=self.num_epochs,
            hyperparams=config,
            round=config["curr_round"],
        )

        return (
            self.get_parameters({}),
            len(self.train_loader),
            {}, 
        )
    def evaluate(self, parameters: NDArrays, config: Dict[str, Scalar]) -> Tuple[int, float, Dict]:
        """Evaluate the network on the test set."""
        self._set_parameters(parameters)
        print(f"Client {self.cid} Evaluating...")

        return (
            len(self.test_dataset[self.cid]),
            train.test(self.net, self.test_dataset[self.cid], self.device),
            {},
        )

def gen_client_fn(
    train_loaders: List[DataLoader],
    model: DictConfig,
    num_epochs: int,
    args: Dict,
    test_loader: Optional[List[DataLoader]]=None,
    state_path: Optional[str]=None,    
) -> Callable[[str], fl.client.NumPyClient]:
    """Return a function which creates a new FlowerClient for a given cid."""

    def client_fn(cid: str) -> fl.client.NumPyClient:
        """Create a new FlowerClient for a given cid."""
        cid = int(cid)
        if args['algorithm'] == "pfedpara" or args['algorithm'] == "fedper":
            return PFedParaClient(
                cid=cid,
                net=instantiate(model).to(args["device"]),
                train_loader=train_loaders[cid],
                test_dataset=copy.deepcopy(test_loader),
                device=args["device"],
                num_epochs=num_epochs,
                state_path=state_path,
            )
        else:
            return FedParaClient(
                cid=cid,
                net=instantiate(model).to(args["device"]),
                train_loader=train_loaders[cid],
                device=args["device"],
                num_epochs=num_epochs,
            )
       
    return client_fn
