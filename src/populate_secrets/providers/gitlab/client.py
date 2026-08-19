import gitlab

from .util import prepare_gitlab_host


def gitlab_client(gitlab_host, gitlab_token):
    return gitlab.Gitlab(prepare_gitlab_host(gitlab_host), private_token=gitlab_token)
