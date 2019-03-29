from pade.acl.aid import AID
from device_agent import DeviceAgent
from pade.misc.utility import start_loop
import sys
import json

if __name__ == '__main__':

    data = json.load(open('data/demo_lv_grid.json'))
    names = [i[0] for i in data['bus']][2:]

    agents = list()
    port = int(sys.argv[1]) 
    for p_id in names:
        name = 'device_agent_' + str(p_id)
        device_agent = DeviceAgent(aid = AID(name=name + '@localhost:' + str(port)),
                                   node_id = p_id)
        device_agent.ams = {'name': 'localhost', 'port': 8001}
        port += 1
        agents.append(device_agent)

    # concentrator_agent = ConcentratorAgent(AID(name='concentrator@localhost:' + str(port)))
    # agents.append(concentrator_agent)

    # port += 1

    # utility_agent = UtilityAgent(AID(name='utility@localhost:' + str(port)))
    # agents.append(utility_agent)

    start_loop(agents)
