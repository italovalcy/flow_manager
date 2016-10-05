import logging
import time

from kyco.constants import POOLING_TIME
from kyco.core.events import KycoEvent
from kyco.core.napps import KycoCoreNApp
from kyco.utils import listen_to
from pyof.foundation.basic_types import HWAddress, UBInt8, UBInt16, UBInt64
from pyof.foundation.network_types import LLDP
from pyof.foundation.constants import UBINT16_MAX_VALUE
from pyof.v0x01.common.action import ActionOutput
from pyof.v0x01.common.constants import NO_BUFFER
from pyof.v0x01.common.flow_match import FlowWildCards, Match
from pyof.v0x01.common.phy_port import Port
from pyof.v0x01.controller2switch.flow_mod import FlowMod, FlowModCommand
from pyof.v0x01.controller2switch.packet_out import PacketOut

log = logging.getLogger('KycoNApp')


class Main(KycoCoreNApp):
    """
    """

    def setup(self):
        """Creates an empty dict to store the switches references and data"""
        self.name = 'kytos/of.lldp'
        self.stop_signal = False
        # TODO: This switches object may change according to changes from #62

    def execute(self):
        """Implement a loop to check switches liveness"""
        while not self.stop_signal:
            for switch in self.controller.switches.values():
                # Gerar lldp para cada uma das portas do switch
                # Gerar o hash de cada um dos pacotes e armazenar

                for port in switch.features.ports:
                    output_action = ActionOutput()
                    output_action.port = port.port_no

                    packet_out = PacketOut()
                    packet_out.actions.append(output_action)
                    packet_out.data = LLDP(port.hw_addr,
                                           switch.dpid,
                                           port.port_no).pack()
                    event_out = KycoEvent()
                    event_out.name = 'kytos/of.lldp.messages.out.ofpt_packet_out'
                    event_out.content = {'destination': switch.connection,
                                         'message': packet_out}
                    self.controller.buffers.msg_out.put(event_out)

                    log.debug("Sending a LLDP PacketOut to the switch %s",
                              switch.dpid)

            # wait 1s until next check...
            time.sleep(POOLING_TIME)

    @listen_to('kytos/of.core.messages.in.ofpt_packet_in')
    def update_lldp(self, event):
        log.debug("PacketIn Received")
        packet_in = event.message
        # ethernet_frame = packet_in.data

    @listen_to('kyco/core.switches.new')
    def install_lldp_flow(self, event):
        """Install initial flow to forward any lldp to controller.

        Args:
            event (KycoSwitchUp): Switch connected to the controller
        """
        switch = event.content['switch']
        log.debug("Installing LLDP Flow on Switch %s",
                  switch.dpid)

        flow_mod = FlowMod()
        flow_mod.command = FlowModCommand.OFPFC_ADD
        flow_mod.match = Match()
        flow_mod.match.wildcards -= FlowWildCards.OFPFW_DL_DST
        flow_mod.match.wildcards -= FlowWildCards.OFPFW_DL_TYPE
        flow_mod.match.dl_dst = "01:23:20:00:00:01"
        flow_mod.match.dl_type = 0x88cc
        flow_mod.priority = 65000  # a high number TODO: Review
        flow_mod.actions.append(ActionOutput(port=Port.OFPP_CONTROLLER,
                                             max_length=UBINT16_MAX_VALUE))
        event_out = KycoEvent(name='kytos/of.lldp.messages.out.ofpt_flow_mod',
                              content={'destination': switch.connection,
                                       'message': flow_mod})

        self.controller.buffers.msg_out.put(event_out)

    def shutdown(self):
        self.stop_signal = True
