# Auto Reconnaissance

## Description

This app shows how to use the Lattice REST SDK for Python SDKs perform a simulated auto-reconnaissance task.

The program streams all incoming entities with the Entities API, then determines if there is any non-friendly track within a certain distance from an asset.
If this requirement is fulfilled, the auto-reconnaissance system classifies the track disposition as suspicious, and creates an `Investigation` task for the asset to investigate the track.

You will create a pair of entities: a simulated asset, and a simulated track for a demonstration of this process.

## How to run locally

#### Prerequisites
- Python version greater than or equal to 3.9

#### Before you begin

Ensure you have [set up your development environment](https://developer.anduril.com/guides/getting-started/set-up)

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

1. Navigate to the `requirements.txt` file and change the path to the SDKs according to where you have outputted the `entities_api` and `tasks_api` packages. After updating these paths, run the following command:
```bash
pip install -r requirements.txt
```

2. Modify the configuration file for the auto reconnaissance system in `var/config.yml`. This is called by all scripts.
* Replace the following placeholders:
    * `<LATTICE_ENDPOINT>` - Your Lattice environment endpoint without an `https://` protocol prefix.
    * `<LATTICE_CLIENT_ID>` - Your Lattice environment client ID.
    * `<LATTICE_CLIENT_SECRET>` - Your Lattice environment client secret.
    *  `<SANDBOXES_TOKEN>` If you are using Lattice Sandboxes, get this from [Account & Security](https://sandboxes.developer.anduril.com/user-settings) page. For more information on obtaining these tokens, see the [Sandboxes documentation](https://developer.anduril.com/guides/getting-started/sandboxes#get-the-tokens)

* If you would like to change the latitude and longitude of your simulated asset and track, you can do so in the corresponding config files. The **default distance threshold for the auto reconnaissance system is 5 miles**. Ensure that the latitude and longitude inputs for your asset and track are within this distance.
    ```
    latitude: <YOUR_LATITUDE>
    longitude: <YOUR_LONGITUDE>
    ```

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

Here is a screenshot of this in action:
![img](/static/auto_recon_asset_investigate_track_example.png)

Congrats, you've tasked an asset to investigate a track!
