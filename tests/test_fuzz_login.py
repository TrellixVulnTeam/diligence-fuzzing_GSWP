from unittest.mock import MagicMock, Mock, patch

from click.testing import CliRunner
from pytest import mark
from requests_mock import Mocker

from mythx_cli.cli import cli
from mythx_cli.fuzz.faas import FaasClient
from mythx_cli.fuzz.rpc import RPCClient
from mythx_cli.fuzz.run import IDE
from tests.common import write_config

REFRESH_TOKEN_MALFORMED_ERROR = "Refresh Token is malformed. The format is `<auth_endpoint>::<client_id>::<refresh_token>`"


def test_no_keys(tmp_path, truffle_project):
    runner = CliRunner()
    write_config(not_include=["api_key"])
    result = runner.invoke(cli, ["run", f"{tmp_path}/contracts"])

    assert "API key or Refresh Token were not provided." in result.output
    assert result.exit_code != 0


@patch.object(RPCClient, attribute="contract_exists", new=Mock(return_value=True))
@patch.object(RPCClient, attribute="get_seed_state", new=Mock(return_value={}))
@patch(target="mythx_cli.fuzz.run.determine_ide", new=Mock(return_value=IDE.HARDHAT))
@patch(target="mythx_cli.fuzz.run.HardhatJob", new=MagicMock())
@patch(target="mythx_cli.fuzz.run.FaasClient", new=MagicMock())
@mark.parametrize("in_config,", [False, True])
@mark.parametrize("key_type,", ["api_key", "refresh_token"])
def test_provide_api_key(in_config: bool, key_type: str, tmp_path, truffle_project):
    runner = CliRunner()
    if not in_config:
        write_config(not_include=["api_key"])
        result = runner.invoke(
            cli,
            [
                "run",
                f"{tmp_path}/contracts",
                f"--{key_type.replace('_', '-')}",
                "test::1::2",
            ],
        )
    else:
        if key_type == "api_key":
            write_config()
        else:
            write_config(not_include=["api_key"], add_refresh_token=True)
        result = runner.invoke(cli, ["run", f"{tmp_path}/contracts"])
    assert result.exit_code == 0
    assert "You can view campaign here:" in result.output


@patch.object(RPCClient, attribute="contract_exists", new=Mock(return_value=True))
@patch.object(RPCClient, attribute="get_seed_state", new=Mock(return_value={}))
@patch(target="mythx_cli.fuzz.run.determine_ide", new=Mock(return_value=IDE.HARDHAT))
@patch(target="mythx_cli.fuzz.run.HardhatJob", new=MagicMock())
@patch(target="mythx_cli.fuzz.run.FaasClient", new=MagicMock())
@mark.parametrize(
    "refresh_token", ["test::1", "test", "test::::2", "::1::2", "::::2", "1::::"]
)
def test_wrong_refresh_token(refresh_token: str, tmp_path):
    runner = CliRunner()
    write_config(not_include=["api_key"])
    result = runner.invoke(
        cli, ["run", f"{tmp_path}/contracts", "--refresh-token", refresh_token]
    )
    assert result.exit_code == 2
    assert REFRESH_TOKEN_MALFORMED_ERROR in result.output


@patch.object(RPCClient, attribute="contract_exists", new=Mock(return_value=True))
@patch.object(RPCClient, attribute="get_seed_state", new=Mock(return_value={}))
@patch.object(FaasClient, attribute="create_faas_campaign", new=Mock())
@patch(target="mythx_cli.fuzz.run.determine_ide", new=Mock(return_value=IDE.HARDHAT))
@patch(target="mythx_cli.fuzz.run.HardhatJob", new=MagicMock())
@mark.parametrize("return_error,", [True, False])
def test_retrieving_api_key(requests_mock: Mocker, return_error: bool, tmp_path):
    requests_mock.real_http = True
    if return_error:
        requests_mock.post(
            "https://example-us.com/oauth/token",
            status_code=403,
            json={"error": "some_error", "error_description": "some description"},
        )
    else:
        requests_mock.post(
            "https://example-us.com/oauth/token",
            status_code=200,
            json={"access_token": "test_access_token"},
        )
    runner = CliRunner()
    write_config(not_include=["api_key"])
    result = runner.invoke(
        cli,
        [
            "run",
            f"{tmp_path}/contracts",
            "--refresh-token",
            "example-us.com::test-ci::test-rt",
        ],
    )

    if return_error:
        assert result.exit_code == 1
        assert "Authorization failed. Error: some_error" in result.exception.message
    else:
        assert result.exit_code == 0
        assert "You can view campaign here:" in result.output
