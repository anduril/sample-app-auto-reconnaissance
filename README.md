# Auto Reconnaissance

## Description

This app demonstrates how to use the Lattice REST SDK for Python SDKs perform a simulated auto-reconnaissance scenario.

This is comprised of three independent programs that work in conjunction; 
1. `simulated_track`: Publishes a representative Track, representing a real-world object that can't be commanded, such as a point-of-interest from a sensor. 
1. `simulated_asset`: Simulates an aerial vehicle that can be tasked to Orbit a point of interest. This uses the Orbit task, defined in `tasks/sim_asset_tasks.proto`
1. `auto-reconnaissance`: Tasks the simulated asset based on the location of the simulated track. This demonstrates how to create Tasks to control Agents in Lattice. 

The program streams all incoming entities with the Entities API, then determines if there is any non-friendly track within a certain distance from an asset.
If this requirement is fulfilled, the auto-reconnaissance system classifies the track disposition as suspicious, and creates an `Orbit` task for the asset to loop around the track.

## How to run locally

#### Prerequisites
- Python version greater than or equal to 3.13

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

* You can change the location of your simulated asset and track from the `var/config.yml` file. The **default distance threshold for the auto reconnaissance system is 5 miles**. Ensure that the latitude and longitude inputs for your asset and track are within this distance.

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


You can view a comprehensive description of the Entities and Tasks in this app from the Developer Console (`https://<your_sandbox_url>/developer-console`). 
![img](/static/auto-recon-orbit-dev-console.png)

While the Task is executing, you can also observe the Asset orbiting the Track via the UI (`https://<your_sandbox_url>/c2`).
![img](/static/auto-recon-orbit-c2-ui.png)


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

## Tasking Breakdown 

The workflow in this app centers around the Orbit task, which defines the information the Asset requires to execute an Orbit action. The main `auto-reconnaissance` program watches the COP and determines if the 
Asset is in range of a Track. Once that condition is satisfied, it creates an Orbit task and delivers it to the Asset using the Tasking APIs.


### Orbit Task Schema 

The Orbit message is defined in `tasks/sim_asset_tasks.proto`, and has been published to the [sample-app-auto-reconnaissance](https://schema-registry.developer.anduril.com/anduril/sample-app-auto-reconnaissance) repo in the Anduril Schema Registry (ASR). See the [ASR docs](https://developer.anduril.com/guides/developer-tools/registry) for more info on how to register schema definitions with Lattice. 

We use the [generated jsonschemas](https://schema-registry.developer.anduril.com/anduril/sample-app-auto-reconnaissance/sdks/main:bufbuild/protoschema-jsonschema) from the ASR to form the Orbit task object in `simulated_asset/tasker.py` and to perform runtime validation when the Asset receives the Task in `simulated_asset/orbit.py`. A snapshot of the generated jsonschemas can be found in `tasks/jsonschema`.
