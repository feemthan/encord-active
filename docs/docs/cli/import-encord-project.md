---
sidebar_position: 3
---

# Importing Encord Project

If you already have a project on the Encord platform, you can import that project with the following command:

```
encord-active import project
```

:::note

This will import a project to new folder in your current working directory. If you prefer to specify a different directory, use:

```shell
encord-active import project --targe /path/to/store/project
```

:::

:::tip

If you don't have an Encord project already, you can either

1. [Initialise a project from a local data directory](/cli/initialising-project-from-image-directories)
2. [Migrating data and labels to Encord](sdk/migrating-data) before calling this command
3. [Download one of our sandbox datasets](/cli/download-sandbox-data)

:::

:::info

If you are new to the Encord platform, you can easily [sign up](https://app.encord.com/register) for an Encord account.

:::

To be able to import an Encord project, you will need the path to your private `ssh-key` associated with Encord (see documentation [here](https://docs.encord.com/admins/settings/public-keys/#set-up-public-key-authentication)).

The command will ask you:

1. `Where is your private ssh key stored?`: type the path to your private ssh key
2. `What project would you like to import?`: here, you can (fuzzy) search for the project title that you would like to import. Hit <kbd>enter</kbd> when your desired project is highlighted.

Next, `encord-active` will fetch your data and labels before computing all the [metrics](category/metrics) available in `encord-active`.

Downloading the data and computing the metrics may take a while.
Bare with us, it is worth the wait.

When the process is done, follow the printed instructions to open the app or see more details in the [Open Encord Active](/cli/open-encord-active) page.
