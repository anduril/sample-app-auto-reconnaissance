# Auto Reconnaissance

## Description

This is a sample application showcasing how to use Lattice HTTP SDKs to perform Entity Auto Reconnaissance.

The program streams all incoming entities with the Entities API, determines if there is any non-friendly track within a certain distance from an asset. If this requirement is fulfilled, the auto reconnaissance system classifies the track disposition as suspicious and creates an investigation task for the asset to investigate the track. You will create a pair of a simulated asset and a track for a clear demonstration of this process.

The following endpoints are showcased in this application:

- the [`long_poll_entity_events`](https://docs.anduril.com/reference/rest/entitymanager/long-poll-entity-events) Entities API endpoint to long poll for incoming entities.
- the [`publish_entity_rest`](https://docs.anduril.com/reference/rest/entitymanager/publish-entity-rest) Entities API endpoint to publish entities.
- the [`put_entity_override_rest`](https://docs.anduril.com/reference/rest/entitymanager/put-entity-override-rest) Entities API endpoint to override certain entity fields.
- the [`create_task`](https://docs.anduril.com/reference/rest/taskmanager/create-task) Tasks API endpoint to create new tasks.
- the [`get_task_by_id`](https://docs.anduril.com/reference/rest/taskmanager/get-task-by-id) Tasks API endpoint to retrieve tasks.
- the [`long_poll_listen_as_agent`](https://docs.anduril.com/reference/rest/taskmanager/long-poll-listen-as-agent) Tasks API endpoint to listen as an agent.
- the [`update_task_status_by_id`](https://docs.anduril.com/reference/rest/taskmanager/update-task-status-by-id) Tasks API endpoint to update a task's status.


## How to run locally

#### Prerequisites
- Python version greater than or equal to 3.9

#### Before you begin

Ensure you have [set up your development environment](https://docs.anduril.com/category/getting-started)

#### Clone the repository

```bash
git clone https://github.com/anduril/sample-app-auto-reconnaissance.git sample-app-auto-reconnaissance
cd sample-app-auto-reconnaissance
```

> Optional: Initialize a virtual environment
> ```bash
> python -m venv .venv
> source .venv/bin/activate
> ```

#### Install dependencies and configure project

Follow the guide [here](https://docs.anduril.com/guide/generate-http-sdks) to generate your Python HTTP SDK.

1. Navigate to the `requirements.txt` file and change the path to the SDKs according to where you have outputted the `entities_api` and `tasks_api` packages. After updating these paths, run the following command:
```bash
pip install -r requirements.txt
```

2. Modify the configuration files for the auto reconnaissance system in `auto-reconnaissance/var/config.yml`, the simulated asset in `simulated_asset/var/config.yml`, and the simulated track in `simulated_track/var/config.yml`.
* Replace `<YOUR_LATTICE_IP>` and `<YOUR_LATTICE_BEARER_TOKEN>` with your Lattice IP and Lattice Bearer Token
```
lattice-ip: <YOUR_LATTICE_IP>
lattice-bearer-token: <YOUR_LATTICE_BEARER_TOKEN>
```
* If you would like to change the latitude and longitude of your simulated asset and track, you can do so in the corresponding config files. The default distance threshold for the auto reconnaissance system is 5 miles. Ensure that the latitude and longitude inputs for your asset and track are within this distance.
```
latitude: <YOUR_LATITUDE>
longitude: <YOUR_LONGITUDE>
```

#### Run the program

Open separate terminals to run the following commands. If you are using a virtual environment, ensure that the virtual environment is activated for all terminals.

```bash
python auto-reconnaissance/main.py --config auto-reconnaissance/var/config.yml
```

```bash
python simulated_asset/asset.py --config simulated_asset/var/config.yml
```

```bash
python simulated_track/track.py --config simulated_track/var/config.yml
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

Here is a screenshot of this in action:
![img](/static/auto_recon_asset_investigate_track_example.png)

Congrats, you've tasked an asset to investigate a track!
