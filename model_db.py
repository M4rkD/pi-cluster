from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, ForeignKey, PickleType, Float
from sqlalchemy import desc
from sqlalchemy.sql import select
import status_codes
import numpy as np
import utils
import settings
import os
import subprocess
import random
from PIL import Image

engine = create_engine('sqlite:///db.sql', echo=True)

# Creates tables if the don't exist
metadata = MetaData()

simulations = Table('runs', metadata, Column('id', Integer, primary_key=True),
                    Column('name', String), Column('email', String),
                    Column('avatar', Integer), Column('rgb', PickleType),
                    Column('rgb_with_contour', PickleType),
                    Column('depth', PickleType),
                    Column('background', PickleType),
                    Column('contour', PickleType), Column('drag', Float),
                    Column('status', Integer))

metadata.create_all(engine)


def save_simulation(sim):
    """
    Save the images from a simulation. This is intended to be called before starting a simulation
    """

    simdir = model.run_directory(sim['id'])

    # Save rgb image with contour
    filename = '{simdir}/rgb_with_contour.png'.format(simdir=simdir)
    save_image(sim['rgb_with_contour'], filename)

    # Save depth image
    filename = '{simdir}/depth.png'.format(simdir=simdir)
    save_image(sim['depth'], filename)


def save_image(img, filename):
    """
    Save the image given by an BGR numpy array as an image in a given location
    """
    rgb = np.uint8(img)
    rgb = rgb[:, :, ::-1]
    i = Image.fromarray(rgb)

    i.save(filename)


def choose_avatar():
    return int(random.random() * 25) + 1


def create_simulation(simulation):
    insert = simulations.insert().values(
        name=simulation['name'],
        email=simulation['email'],
        avatar=choose_avatar(),
        rgb=simulation['rgb'],
        rgb_with_contour=simulation['rgb_with_contour'],
        depth=simulation['depth'],
        background=simulation['background'],
        contour=simulation['contour'],
        status=status_codes.SIMULATION_WAITING)

    result = engine.execute(insert)

    rowid = result.lastrowid

    # row id required by save_simulation to determine file location
    simulation['id'] = rowid
    save_simulation(simulation)

    return rowid


def all_simulations():
    sql = simulations.select()

    results = engine.execute(sql)

    return results_to_simulation(results)


def waiting_simulations():
    return simulations_by_status(status_codes.SIMULATION_WAITING)


def set_started(sim_id):
    set_simulation_status(sim_id, status_codes.SIMULATION_STARTED)


def simulations_by_status(status):
    sql = simulations.select().where(simulations.c.status == status)

    results = engine.execute(sql)

    sims = results_to_simulation(results)

    # results_to_simulation returns a dictionary with IDs as keys, we just want a list
    sims = [sims[key]['id'] for key in sims.keys()]

    return sims


def set_simulation_status(sim_id, status):
    sql = simulations.update().where(simulations.c.id == sim_id).values(
        status=status_codes.SIMULATION_STARTED)

    results = engine.execute(sql)

    return results


def results_to_simulation(results):

    results = [dict(row) for row in results]

    # index by ID
    results = {row['id']: row for row in results}

    return results


def get_simulation(id):
    sql = simulations.select().where(simulations.c.id == id)

    results = engine.execute(sql)

    results = results_to_simulation(results)

    result = results[int(id)]

    return result


def write_outline(filename, outline):
    "Takes an outline as an array and saves it to file outline file"
    outline = np.array(outline)
    flipped_outline = np.copy(outline.reshape((-1, 2)))
    flipped_outline[:, 1:] = 480 - flipped_outline[:, 1:]
    np.savetxt(filename, flipped_outline, fmt='%i %i')


def run_simulation(sim_id, hostfilename):

    simulation = get_simulation(sim_id)

    set_started(sim_id)

    run_dir = run_directory(sim_id)

    utils.ensure_exists(run_dir)

    outline_coords = '{run_dir}/outline-coords.dat'.format(run_dir=run_dir)

    write_outline(outline_coords, simulation['contour'])

    outfile = '{run_dir}/output'.format(run_dir=run_dir)

    command = settings.cfdcommand.format(id=sim_id,
                                         ncores=settings.nodes_per_job *
                                         settings.cores_per_node,
                                         hostfile=hostfilename,
                                         output=outfile)

    print(f'RUNNING SIMULATION #{sim_id}: {command}'.format(sim_id=sim_id, command=command)
    process = subprocess.Popen(command, shell=True)

    return process


def set_drag(sim_id, drag):
    sql = simulations.update().where(simulations.c.id == sim_id).values(
        drag=drag)

    results = engine.execute(sql)

    return results


def run_directory(index):
    directory = '{root}/simulations/{index}'.format(root=settings.root_dir,index=index)

    utils.ensure_exists(directory)

    return directory


def outline_coords_file(sim_id):
    return '{dir}/outline-coords.dat'.format(dir=run_directory(sim_id))


def highest_drag_simulations_sorted(num_sims):
    "fetches all the simulations and orders them by value of drag"

    sql = select([
        simulations.c.id, simulations.c.name, simulations.c.drag,
        simulations.c.avatar
    ]).where(simulations.c.status == status_codes.SIMULATION_STARTED).order_by(
        desc(simulations.c.drag))

    return _select_num_sims_by_sql(sql, num_sims)


def recent_simulations(num_sims):
    "fetches the num_sims simulations with the highest ID"

    sql = select([
        simulations.c.id, simulations.c.name, simulations.c.drag,
        simulations.c.avatar
    ]).where(simulations.c.status == status_codes.SIMULATION_STARTED).order_by(
        desc(simulations.c.id))

    return _select_num_sims_by_sql(sql, num_sims)


def _select_num_sims_by_sql(sql, num_sims):
    results = engine.execute(sql)

    sorted_sims = [{
        'id': row['id'],
        'name': row['name'],
        'drag': row['drag'],
        'avatar': row['avatar'],
    } for row in results]

    if len(sorted_sims) >= num_sims:
        sorted_sims = sorted_sims[:num_sims]

    return sorted_sims