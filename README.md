# Auto Reconnaissance

## Description

This sample application demonstrates how to use REST APIs in the Lattice SDK to create and manage tasks in a simulated reconnaisance scenario.

The program streams all incoming entities with the Entities API. If there is any non-friendly track within a certain distance from a friendly asset, the auto reconnaissance system classifies the track disposition as suspicious and creates an investigation task assigned to the asset. You will create a pair of a simulated asset and a track for a clear demonstration of this process.

The following endpoints are showcased in this application:

- the [`long_poll_entity_events`](https://developer.anduril.com/reference/rest/entities/long-poll-entity-events) Entities API endpoint to long poll for incoming entities.
- the [`publish_entity`](https://developer.anduril.com/reference/rest/entities/publish-entity) Entities API endpoint to publish entities.
- the [`override_entity`](https://developer.anduril.com/reference/rest/entities/override-entity) Entities API endpoint to override certain entity fields.
- the [`create_task`](https://developer.anduril.com/reference/rest/tasks/create-task) Tasks API endpoint to create new tasks.
- the [`get_task`](https://developer.anduril.com/reference/rest/tasks/get-task) Tasks API endpoint to retrieve tasks.
- the [`listen_as_agent`](https://developer.anduril.com/reference/rest/tasks/listen-as-agent) Tasks API endpoint to listen as an agent.
- the [`update_task_status`](https://developer.anduril.com/reference/rest/tasks/update-task-status) Tasks API endpoint to update a task's status.

## Before you begin
- Install Python version greater than or equal to 3.9.
- Complete the [set up](https://developer.anduril.com/guides/getting-started/set-up) instructions in the *Lattice SDK Documentation*.

## Clone the repository

```bash
git clone https://github.com/anduril/sample-app-auto-reconnaissance.git sample-app-auto-reconnaissance
cd sample-app-auto-reconnaissance
```

> Optional: Initialize a virtual environment
> ```bash
> python -m venv .venv
> source .venv/bin/activate
> ```

## Install dependencies and configure project

1. Install Python requirements 
```bash
pip install -r requirements.txt
```

2. Modify the configuration file for the auto reconnaissance system in `var/config.yml`. This is called by all scripts.
* Replace the following placeholders:
    * `<LATTICE_ENDPOINT>` - hostname, Lattice URL without `https://` protocol prefix
    * `<ENVIRONMENT_TOKEN>` - Token for your Lattice environment
    * `<SANDBOXES_TOKEN>` - if using Lattice Sandboxes, see the [Sandboxes guide](https://developer.anduril.com/guides/getting-started/sandboxes)

* If you would like to change the latitude and longitude of your simulated asset and track, you can do so in the corresponding config files. The **default distance threshold for the auto reconnaissance system is 5 miles**. Ensure that the latitude and longitude inputs for your asset and track are within this distance.

#### Run the program

Open separate terminals to run the following commands. If you are using a virtual environment, ensure that the virtual environment is activated for all terminals.

```bash
python auto-reconnaissance/main.py --config var/config.yml
```

```bash
python simulated_asset/asset.py --config var/config.yml
```

```bash
python simulated_track/track.py --config var/config.yml
```

Navigate to your Lattice UI and observe the `Active Tasks` tab. When assets come within range of a non-friendly track, an investigation task will be created. If you observe the simulated asset and track, you will see that the auto reconnaissance system will classify the track disposition as suspicious, and a task will be created for the asset to investigate the track. 

On the console, you will see the auto reconnaissance system creating a task:
```
INFO:EARS:ASSET WITHIN RANGE OF NON-FRIENDLY TRACK
INFO:EARS:overriding disposition for track $ENTITY_ID
INFO:EARS:Task created - view Lattice UI, task id is $TASK_ID
```

Simultaneously, you will see the simulated asset receive the execute request:
```
INFO:SIMASSET:received execute request, sending execute confirmation
```

Afterwards, the auto reconnaissance system will continuously check the status of any tasks being executed.

Navigate to your Lattice UI and verify that the simulated asset and simulated track are displayed.
![img](/static/auto_recon_asset_investigate_track_example.png)

