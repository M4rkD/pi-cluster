import numpy as np
import glob
import re
import utils
import settings
import os
import subprocess
import pickle
from PIL import Image
import glob
import random
from repoze.lru import lru_cache

from jinja2 import Template

######################################
## Package variables
######################################

STATUS_CREATED = 'status.created'

# This is also set in the batch file
STATUS_STARTED = 'status.started'
STATUS_FINISHED = 'status.finished'
STATUS_TOPRINT = 'status.toprint'

# Read batch template file if exists
template_file = 'templates/slurm.batch'
if os.path.isfile(template_file):
    with open(template_file) as f:
        BATCH_TEMPLATE = Template(f.read())

######################################
## Paths
######################################


def clean_sim_id(sim_id):
    return int(sim_id)


def sim_filepath(simulation_id, filename):
    return run_directory(simulation_id) + '/' + filename


def sim_datafile(simulation_id):
    return sim_filepath(simulation_id, 'data.pickle')


def run_directory(index):
    directory = '{sim_dir}/{index}'.format(
        sim_dir=simulation_store_directory(), index=index)

    utils.ensure_exists(directory)

    return directory


def simulation_store_directory():
    directory = '{root_dir}/simulations'.format(root_dir=settings.root_dir)

    utils.ensure_exists(directory)

    return directory


def drag_file(sim_id):
    return sim_filepath(sim_id, 'drag.txt')


def touch_file(sim_id, filename):
    open(sim_filepath(sim_id, filename), 'a').close()


def sim_check_file(sim_id, filename):
    return os.path.isfile(sim_filepath(sim_id, filename))


def check_status(sim_id, status):
    return sim_check_file(sim_id, status)


def set_started(sim_id, job_id):
    with open(sim_filepath(sim_id, STATUS_STARTED), 'w') as f:
        f.write(job_id)


def set_finished(sim_id):
    touch_file(sim_id, STATUS_FINISHED)


######################################
## Pickle and save/load utils
######################################


def pickle_save(filename, data):
    """
    Pickles data to a given filename. Note, it writes using a temporary file to
    avoid that file is read before finished writing.
    """

    filename_tmp = filename + 'tmp'

    with open(filename_tmp, 'wb') as f:
        pickle.dump(data, f, 2)

    os.rename(filename_tmp, filename)

    return data


@lru_cache(maxsize=20)
def pickle_load(filename):
    """
    Loads objects from a pickle file with cache. Note, care should be taken not to
    attempt to cause invalid cache entries. The datastore is treated as immutable.
    """
    with open(filename, 'rb') as f:
        sim = pickle.load(f)

    return sim


def save_data_as_image(data, filename):
    """
    Save the image given by an BGR numpy array as an image in a given location
    """
    rgb = np.uint8(data)
    rgb = rgb[:, :, ::-1]
    i = Image.fromarray(rgb)

    i.save(filename)


######################################
## Utils
######################################


def choose_avatar():
    return int(random.random() * 25) + 1


def generate_sim_id():
    current_ids = simulation_id_list()

    if len(current_ids) == 0:
        next_id = 1
    else:
        next_id = int(np.max(current_ids) + 1)

    return next_id


def simulation_id_list():
    sim_store = simulation_store_directory()
    return [
        clean_sim_id(os.path.basename(i))
        for i in glob.glob('{sim_store}/[0-9]*'.format(sim_store=sim_store))
    ]


def is_sim_running(sim_id):
    sim_id = clean_sim_id(sim_id)

    return check_status(
        sim_id, STATUS_STARTED) and not check_status(sim_id, STATUS_FINISHED)


def is_sim_finished(sim_id):
    sim_id = clean_sim_id(sim_id)

    return check_status(sim_id, STATUS_FINISHED)


def is_sim_queued(sim_id):
    sim_id = clean_sim_id(sim_id)

    return check_status(
        sim_id, STATUS_CREATED) and not check_status(sim_id, STATUS_STARTED)


def get_drag(sim_id):
    filename = drag_file(sim_id)

    if os.path.isfile(filename):
        with open(filename) as file:
            return float(file.read())
    else:
        return None


def all_drags():
    ids = np.array(simulation_id_list())
    drags = np.array([get_drag(i) for i in ids])

    notNone = [i for i in range(len(drags)) if drags[i] is not None]

    ids = ids[notNone].astype(np.int32)
    drags = drags[notNone].astype(np.int32)

    return (drags, ids)


def sims_by_id(ids):
    return [get_simulation(sim) for i in simulation_id_list()]


def set_drag(sim_id, drag):
    filename = drag_file(sim_id)

    with open(filename, 'w') as file:
        file.write(str(drag))


def write_batch_script(sim_id):
    batch_contents = BATCH_TEMPLATE.render(sim_id=sim_id,
                                           start_file=STATUS_STARTED,
                                           end_file=STATUS_FINISHED,
                                           root_dir=settings.root_dir)

    filename = sim_filepath(sim_id, 'slurm.batch')

    with open(filename, 'w') as f:
        f.write(batch_contents)

    return filename


def get_nodes(sim_id):
    """
    If slurm.hosts file exists (as written by the jobscript), then return a list of the node
    IP addresses found in the file for simulation with ID `sim_id`. If the hosts file does not exist return an empty list.
    """
    filepath = sim_filepath(sim_id, 'slurm.hosts')
    if os.path.isfile(filepath):
        with open(filepath, 'r') as f:
            lines = f.readlines()

        ips = [line.split()[0] for line in lines]
    else:
        ips = []

    return ips


######################################
## Printing
######################################

def set_toprint(sim_id):
    """
    Mark a job as ready for printing
    """

    touch_file(sim_id, STATUS_TOPRINT)


def mark_as_printed(sim_id):
    """
    Mark a job as printed
    """

    filepath = sim_filepath(sim_id, STATUS_TOPRINT)

    if os.path.isfile(filepath):
        os.remove(filepath)


def find_to_print():
    paths = glob.glob("{dir}/*/status.toprint".format(dir=simulation_store_directory()))

    if len(paths) > 0:
        print_ids = [int(path.split('/')[-2]) for path in paths]
    else:
        print_ids = []

    return sorted(print_ids)


def next_to_print():
    """
    Returns next print job, otherwise returns None
    """
    to_print = find_to_print()

    if len(to_print) > 1:
        return to_print[0]
    else:
        return None


######################################
## Public API
######################################


def valid_simulations(id_list):
    # get_simulation can return None if a non-simulation directory exists in
    # simulations or if the pickle file is half-written

    return [s for s in [get_simulation(i) for i in id_list] if s is not None]


def all_simulations():
    return valid_simulations(simulation_id_list())


def queued_simulations():
    """
    Returns a list of IDs of queued simulations, in their order in the queue.
    The last to be added is returned first.
    """

    ids = [s for s in simulation_id_list() if is_sim_queued(s)]
    ids.sort(reverse=True)

    return ids


def running_simulations():
    """
    Returns a list of IDs of running simulations, most recently started first
    """
    ids = [s for s in simulation_id_list() if is_sim_running(s)]
    ids.sort(reverse=True)

    return ids


def get_progress(sim_id):
    """
    Read the completion percentage of the run by using grep and the output file and
    counting the completed steps and jobsteps. Each jobstep (i.e. "Starting Step"
    string appearing in the output file) is equivalent progress to completing
    a timestep of the simulation. Whilst this is not true in general, it allows a
    simple measure of total progress.
    """

    percentage = 0

    outputfile = sim_filepath(sim_id, 'slurm.output')

    if os.path.isfile(outputfile):
        cmd = 'grep "MAIN:  Time:" {file}'.format(file=outputfile)

        # Count simulation steps
        try:
            output = subprocess.check_output(
                ["grep", "MAIN:  Time", outputfile]).decode('utf-8')
            completed_steps, total_steps = output.splitlines()[-1].split(
            )[2].split("/")

        except subprocess.CalledProcessError as e:
            # grep returns an error if nothing found
            completed_steps = 0
            total_steps = settings.number_timesteps

        # Convert strings to ints
        completed_steps = int(completed_steps)
        total_steps = int(total_steps)

        # Ignore the last step, this is accounted for in the jobstep finishing
        if completed_steps == total_steps:
            completed_steps = total_steps - 1
            total_steps = total_steps - 1

        # Count job steps (could break if anyone changes output file text)
        total_jobsteps = settings.jobstep_count

        try:
            output = subprocess.check_output(
                ["grep", "Starting Step [0-9]", outputfile]).decode('utf-8')

            completed_jobsteps = len(output.splitlines())

        except subprocess.CalledProcessError as e:
            # grep returns an error if nothing found
            completed_jobsteps = 0

        # Compute completion percentage
        done = float(completed_steps + completed_jobsteps)
        todo = float(total_steps + total_jobsteps)

        percentage = int(100 * done / todo)

    return percentage


def get_simulation_detail_key(sim_id, key):
    filepath = sim_filepath(sim_id, 'all_data.pickle')

    if os.path.isfile(filepath):
        with open(filepath, 'rb') as f:
            sim = pickle.load(f)
            val = sim[key]
        return val
    else:
        print("key simulation key: file {filepath} not found".format(
            filepath=filepath))
        return None


def get_simulation(sim_id):
    """
    Returns simulation data for a simulation if the data file exists and the created flag exists. Otherwise returns None.
    """
    sim_id = clean_sim_id(sim_id)

    datafile = sim_datafile(sim_id)

    simulation = None

    # Read the info about simulation if it has been created
    if check_status(sim_id, STATUS_CREATED) and os.path.isfile(datafile):
        simulation = pickle_load(datafile)
        simulation['drag'] = get_drag(sim_id)

        # set the images available key for simulation
        simulation['images-available'] = sim_check_file(
            sim_id, 'rgb_with_contour.png') and sim_check_file(
                sim_id, 'depth.png')

        simulation['nodes'] = get_nodes(sim_id)
        simulation['avatar_id'] = get_avatar_id(sim_id)

        simulation['progress'] = get_progress(sim_id)

        # force the simulation ID (in case files have been moved around manually)
        simulation['id'] = sim_id

    return simulation


def write_outline(sim_id, outline):
    "Takes an outline as an array and saves it to file outline file"
    filename = outline_coords_file(sim_id)
    outline = np.array(outline)
    flipped_outline = np.copy(outline.reshape((-1, 2)))
    flipped_outline[:, 1:] = 480 - flipped_outline[:, 1:]
    np.savetxt(filename, flipped_outline, fmt='%i %i')


def queue_simulation(sim):
    """
    Creates the simulation data files and submits the simulation to the queue manager
    """

    # Ensure that simulation has an ID
    if 'id' not in sim.keys():
        sim['id'] = generate_sim_id()

    sim_id = sim['id']

    write_outline(sim_id, sim['contour'])
    batch_script = write_batch_script(sim_id)

    # Write avatar to file and add to sim dictionary for writing
    avatar_id = get_next_avatar()
    write_avatar(sim_id, avatar_id)
    sim['avatar_id'] = avatar_id

    # Submit the job to SLURM
    if settings.devel:
        # In development, just return a job ID
        print('WARNING: Not submitting batch script in development')
        job_id = '123'
    else:
        cmd = 'cd ~/ && sbatch {script}'.format(script=batch_script)
        output = subprocess.check_output(cmd, shell=True).decode('utf8')

        job_id = re.match('^Submitted batch job ([0-9]*)', output).group(1)

        # Write job id to file
    with open(sim_filepath(sim_id, 'job_id'), 'w') as f:
        f.write(job_id)

    print('RUNNING SIMULATION: {sim_id}'.format(sim_id=sim_id))

    # Save data files for the simulation
    filename = sim_datafile(sim['id'])

    pickle_save(filename, sim)

    touch_file(sim_id, STATUS_CREATED)

    return sim_id


def outline_coords_file(sim_id):
    return sim_filepath(sim_id, 'outline-coords.dat')


def lowest_drag_simulations_sorted(num_sims=10):
    "fetches `num_sims` simulations and order them by value of drag"

    drags, sim_ids = all_drags()
    idxs = np.argsort(drags)[:num_sims][::-1]

    result_sim_ids = sim_ids[idxs]

    return valid_simulations(result_sim_ids)


def recently_finished_simulations(num_sims=10):
    "fetches `num_sims` simulations with the highest ID"

    recent_sim_ids = [
        sim_id for sim_id in simulation_id_list() if is_sim_finished(sim_id)
    ]
    sorted_sim_ids = sorted(recent_sim_ids, reverse=True)[:num_sims]

    return valid_simulations(sorted_sim_ids)


######################################
## Avatars
######################################


def avatar_file(sim_id):
    return sim_filepath(sim_id, 'avatar_id')


def get_avatar_id(sim_id):
    """
    Return the avatar id for a given simulation
    """

    filename = avatar_file(sim_id)

    if os.path.exists(filename):
        with open(avatar_file(sim_id), 'r') as f:
            return int(f.readline())
    else:
        return 0


def get_available_avatars(num_leaderboard=10):
    # fetch required info
    running = running_simulations()
    queued = queued_simulations()

    # leaderboard returns a dict, we extract the ID key as an int
    leaderboard_sims = lowest_drag_simulations_sorted(num_sims=num_leaderboard)
    leaderboard = [int(s['id']) for s in leaderboard_sims]

    # IDs still visible in the UI
    visible_ids = set(running + queued + leaderboard)

    used_avatars = set([get_avatar_id(s) for s in visible_ids])

    # work out the available avatars
    available_avatars = set(range(1, 26)) - used_avatars
    return available_avatars


def choose_avatar(available):
    return random.choice(tuple(available))


def get_next_avatar(num_leaderboard=10):
    # pick a random one
    available_avatars = get_available_avatars(num_leaderboard)
    return choose_avatar(available_avatars)


def write_avatar(sim_id, avatar_id):
    with open(avatar_file(sim_id), 'w') as f:
        f.write(str(avatar_id))
