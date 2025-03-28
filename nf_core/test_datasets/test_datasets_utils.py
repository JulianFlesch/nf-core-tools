import asyncio
import json
import logging
from dataclasses import dataclass

import aiohttp
import requests
from utils import gh_api

log = logging.getLogger(__name__)

@dataclass
class GithubApiEndpoints():
    gh_api_base_url = "https://api.github.com"
    gh_orga: str = "nf-core"
    gh_repo: str = "test-datasets"

    def get_branch_list_url(self, entries_per_page=300):
        # TODO: If more branches than entries_per_page exist, pagination must be dealt with!
        url = f"{self.gh_api_base_url}/repos/{self.gh_orga}/{self.gh_repo}/branches?per_page={entries_per_page}"
        return url

    def get_remote_tree_url_for_branch(self, branch, recursive=1):
        url = f"{self.gh_api_base_url}/repos/{self.gh_orga}/{self.gh_repo}/git/trees/{branch}?recursive=1"
        return url

class GithubApiSessionAsync(aiohttp.ClientSession):
    def __init__(self, gh_api, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gh_api = gh_api
        self.setup_github_auth(self)

    def setup_github_auth(self, auth=None):

        if self.gh_api.auth is None:
            self.gh_api.setup_github_auth()

        if isinstance(self.gh_api.auth, requests.auth.HTTPBasicAuth):
            self.auth = aiohttp.BasicAuth(self.gh_api.auth.login, self.gh_api.auth.password)
        elif isinstance(self.gh_api.auth, requests.auth.AuthBase):
            if self.headers is None:
                self.headers = dict()

            self.headers["authorization"] = f"Bearer {self.gh_api.auth.token}"

        else:
            log.debug("Auth could not be transfered to GithubApiSessionAsync")


def get_remote_branches():
    """
    List all branches on the remote github repository for test-datasets
    by querying the github API endpoint at `/repos/nf-core/test-datasets/branches`
    """
    try:
        gh_api_urls = GithubApiEndpoints(gh_repo="test-datasets")
        response = gh_api.get(gh_api_urls.get_branch_list_url())

        if not response.ok:
            log.error(f"Error status code {response.status_code} received while fetching the list of branches at url: {response.url}")
            return []

        resp_json = json.loads(response.text)
        branches = [b["name"] for b in resp_json]

    except requests.exceptions.RequestException as e:
        log.error("Error while handling request to url {gh_api_url}", e)
    except KeyError as e:
        log.error("Error parsing the list of branches received from Github API", e)
    except json.decoder.JSONDecodeError as e:
        log.error("Error parsing the list of branches received from Github API at url {response.url} as json",  e)

    return branches


def get_remote_tree_for_branch(branch, only_files=True, ignored_prefixes=[]):
    """
    For a given branch name, return the file tree by querying the github API
    at the endpoint at `/repos/nf-core/test-datasets/git/trees/`
    """
    gh_filetree_file_value = "blob"    # value in nodes used to refer to "files"
    gh_response_filetree_key = "tree"  # key in response to refer to the filetree
    gh_filetree_type_key = "type"      # key in filetree nodes used to refer to their type
    gh_filetree_name_key = "path"      # key in filetree nodes used to refer to their name

    try:
        gh_api_url = GithubApiEndpoints(gh_repo="test-datasets")
        response = gh_api.get(gh_api_url.get_remote_tree_url_for_branch(branch))

        if not response.ok:
            log.error(f"Error status code {response.status_code} received while fetching the repository filetree at url {response.url}")
            return []

        repo_tree = json.loads(response.text)[gh_response_filetree_key]

        if only_files:
            repo_tree = [node for node in repo_tree if node[gh_filetree_type_key] == gh_filetree_file_value]

        # filter by ignored_prefixes and extract names
        repo_files = []
        for node in repo_tree:
            for prefix in ignored_prefixes:
                if node[gh_filetree_name_key].startswith(prefix):
                    break
            else:
                repo_files.append(node[gh_filetree_name_key])

    except requests.exceptions.RequestException as e:
        log.error("Error while handling request to url {gh_api_url}", e)

    except json.decoder.JSONDecodeError as e:
        log.error("Error parsing the repository filetree received from Github API at url {response.url} as json", e)

    return repo_files


def list_files_by_branch(branch=None, ignored_file_prefixes=[".", "CITATION", "LICENSE", "README", "docs", ]):
    """
    Lists files for all branches in the test-datasets github repo.
    Returns dictionary with branchnames as keys and file-lists as values
    """

    # Fetch list of branches frorm GitHub API
    log.debug("Fetching list of remote branches")
    branches = get_remote_branches()

    if branch:
        branches = list(filter(lambda b: b == branch, branches))
        if len(branches) == 0:
            log.error(f"No branches matching '{branch}'")

    log.debug("Fetching remote trees")
    tree = dict()
    for b in branches:
        tree[b] = get_remote_tree_for_branch(b, only_files=True, ignored_prefixes=ignored_file_prefixes)

    return tree


async def get_remote_tree_for_branch_async(session, branch, only_files=True, ignored_prefixes=[]):
    """
    For a given branch name, return the file tree by querying the github API
    at the endpoint at `/repos/nf-core/test-datasets/git/trees/`
    """
    gh_filetree_file_value = "blob"    # value in nodes used to refer to "files"
    gh_response_filetree_key = "tree"  # key in response to refer to the filetree
    gh_filetree_type_key = "type"      # key in filetree nodes used to refer to their type
    gh_filetree_name_key = "path"      # key in filetree nodes used to refer to their name

    gh_api_url = GithubApiEndpoints(gh_repo="test-datasets")
    async with session.get(gh_api_url.get_remote_tree_url_for_branch(branch)) as response:
        response_json = await response.json()

        if not response.ok:
            log.error(f"Error status code {response.status} received while fetching the repository filetree at url {response.url}")
            return []

        repo_tree = response_json[gh_response_filetree_key]

    if only_files:
        repo_tree = [node for node in repo_tree if node[gh_filetree_type_key] == gh_filetree_file_value]

    # filter by ignored_prefixes and extract names
    repo_files = []
    for node in repo_tree:
        for prefix in ignored_prefixes:
            if node[gh_filetree_name_key].startswith(prefix):
                break
        else:
            repo_files.append(node[gh_filetree_name_key])

    return repo_files


async def list_files_payload_wrapper(branches, ignored_file_prefixes):

    async with GithubApiSessionAsync(gh_api) as session:
        to_execute = [get_remote_tree_for_branch_async(session, b, only_files=True, ignored_prefixes=ignored_file_prefixes) for b in branches]
        tree_list = await asyncio.gather(*to_execute)
        tree = dict(zip(branches, tree_list))

    return tree


def list_files_by_branch_async(branch=None, ignored_file_prefixes=[".", "CITATION", "LICENSE", "README", "docs", ]):
    """
    Lists files for all branches in the test-datasets github repo concurrently.
    Returns dictionary with branchnames as keys and file-lists as values
    """

    # Fetch list of branches frorm GitHub API
    log.debug("Fetching list of remote branches")
    branches = get_remote_branches()

    if branch:
        branches = list(filter(lambda b: b == branch, branches))
        if len(branches) == 0:
            log.error(f"No branches matching '{branch}'")

    log.debug("Fetching remote trees")
    tree = asyncio.run(list_files_payload_wrapper(branches, ignored_file_prefixes))

    return tree
