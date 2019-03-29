import itertools
import random
import json

from mosaik.util import connect_randomly, connect_many_to_one
import mosaik


sim_config = {
    'CSV': {
        'python': 'mosaik_csv:CSV',
    },
    'DB': {
        'cmd': 'mosaik-hdf5 %(addr)s',
    },
    'HouseholdSim': {
        'python': 'householdsim.mosaik:HouseholdSim',
        # 'cmd': 'mosaik-householdsim %(addr)s',
    },
    'PyPower': {
        'python': 'mosaik_pypower.mosaik:PyPower',
        # 'cmd': 'mosaik-pypower %(addr)s',
    },
    'WebVis': {
        'cmd': 'mosaik-web -s 0.0.0.0:8000 %(addr)s',
    },
}

START = '2014-01-01 00:00:00'
END = 2 * 24 * 3600  # 1 day
PV_DATA = 'data/pv_10kw.csv'
PROFILE_FILE = 'data/profiles.data.gz'
GRID_NAME = 'demo_lv_grid'
GRID_FILE = 'data/%s.json' % GRID_NAME
PV_QTD = 20


# -------------------------------------------------
# configura os simuladores de device agents
# -------------------------------------------------

data = json.load(open('data/demo_lv_grid.json'))
agent_names = [i[0] for i in data['bus']][2:]

agent_names = random.sample(agent_names, PV_QTD)

port = 1234
device_agent_sim_names = dict()
for i in agent_names:
    name = 'DeviceAgentSim{}'.format(i)
    device_agent_sim_names[i] = name
    sim_config[name] = {'connect': 'localhost:' + str(port)}
    port += 1


def main():
    random.seed(23)
    world = mosaik.World(sim_config)
    create_scenario(world)
    # world.run(until=END)  # As fast as possilbe
    world.run(until=END, rt_factor=1/(30*60))

def create_scenario(world):
    # Start simulators
    pypower = world.start('PyPower', step_size=15*60)
    hhsim = world.start('HouseholdSim')
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)

    # =======================================
    # inicializa as classes que irão representar
    # cada um dos agentes dispositivos via
    # comunicação com a plataforma PADE
    # =======================================
    device_agent_sim_dict = dict()
    for i, name in device_agent_sim_names.items():
        device_agent_sim = world.start(name,
                                       eid_prefix='DeviceAgent_',
                                       prosumer_ref=i,
                                       start=START,
                                       step_size=1 * 60) # o step de tempo é dado em segundos
        device_agent_sim_dict[i] = device_agent_sim


    # Instantiate models
    grid = pypower.Grid(gridfile=GRID_FILE).children
    houses = hhsim.ResidentialLoads(sim_start=START,
                                    profile_file=PROFILE_FILE,
                                    grid_name=GRID_NAME).children
    pvs = pvsim.PV.create(PV_QTD)

    device_agents = [i.DeviceAgent.create(1)[0] for i in device_agent_sim_dict.values()]

    # Connect entities
    connect_buildings_to_grid(world, houses, grid)
    # connect_randomly(world, pvs, [e for e in grid if 'node' in e.eid], 'P')
    
    buses = [e for e in grid if 'node' in e.eid]
    buses_indexs = random.sample(range(len(pvs)), len(pvs))
    for pv, i in zip(pvs, buses_indexs):
        world.connect(pv, buses[i], 'P')
        world.connect(pv, device_agents[i], 'P')
        world.connect(device_agents[i], buses[i], 'P')
    
    # connect_buildings_to_agents(world, houses, device_agents)

    # Database
    db = world.start('DB', step_size=60, duration=END)
    hdf5 = db.Database(filename='demo.hdf5')
    connect_many_to_one(world, houses, hdf5, 'P_out')
    connect_many_to_one(world, pvs, hdf5, 'P')

    nodes = [e for e in grid if e.type in ('RefBus, PQBus')]
    connect_many_to_one(world, nodes, hdf5, 'P', 'Q', 'Vl', 'Vm', 'Va')

    branches = [e for e in grid if e.type in ('Transformer', 'Branch')]
    connect_many_to_one(world, branches, hdf5,
                        'P_from', 'Q_from', 'P_to', 'P_from')

    # Web visualization
    webvis = world.start('WebVis', start_date=START, step_size=60)
    webvis.set_config(ignore_types=['Topology', 'ResidentialLoads', 'Grid',
                                    'Database'])
    vis_topo = webvis.Topology()

    connect_many_to_one(world, nodes, vis_topo, 'P', 'Vm')
    webvis.set_etypes({
        'RefBus': {
            'cls': 'refbus',
            'attr': 'P',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 30000,
        },
        'PQBus': {
            'cls': 'pqbus',
            'attr': 'Vm',
            'unit': 'U [V]',
            'default': 230,
            'min': 0.99 * 230,
            'max': 1.01 * 230,
        },
    })

    connect_many_to_one(world, houses, vis_topo, 'P_out')
    webvis.set_etypes({
        'House': {
            'cls': 'load',
            'attr': 'P_out',
            'unit': 'P [W]',
            'default': 0,
            'min': 0,
            'max': 3000,
        },
    })

    connect_many_to_one(world, pvs, vis_topo, 'P')
    webvis.set_etypes({
        'PV': {
            'cls': 'gen',
            'attr': 'P',
            'unit': 'P [W]',
            'default': 0,
            'min': -10000,
            'max': 0,
        },
    })

    connect_many_to_one(world, device_agents, vis_topo, 'P')
    webvis.set_etypes({
        'DeviceAgent': {
            'cls': 'storage',
            'attr': 'P',
            'unit': 'P [W]',
            'default': 0,
            'min': -1000,
            'max': 0,
        },
    })


def connect_buildings_to_grid(world, houses, grid):
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, buses[node_id], ('P_out', 'P'))

def connect_buildings_to_agents(world, houses, agents):
    agents = {a.eid.split('-')[1]: a for a in agents}
    house_data = world.get_data(houses, 'node_id')
    # Reiniciar aqui
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, agents[node_id], ('P_out', 'P'))


if __name__ == '__main__':
    main()
