"""NApp that solve the L2 Learning Switch algorithm."""

from kytos.core import KytosEvent, KytosNApp, log
from kytos.core.helpers import listen_to
from pyof.foundation.network_types import Ethernet
from pyof.v0x01.asynchronous.packet_in import PacketInReason
from pyof.v0x01.common.action import ActionOutput
from pyof.v0x01.common.flow_match import Match
from pyof.v0x01.common.phy_port import Port
from pyof.v0x01.controller2switch.flow_mod import FlowMod, FlowModCommand
from pyof.v0x01.controller2switch.packet_out import PacketOut

from napps.legacy.of_l2ls import settings


class Main(KytosNApp):
    """Main class of a KytosNApp, responsible for OpenFlow operations."""

    def setup(self):
        """App initialization (used instead of ``__init__``).

        The setup method is automatically called by the run method.
        Users shouldn't call this method directly.
        """
        pass

    def execute(self):
        """Method to be runned once on app 'start' or in a loop.

        The execute method is called by the run method of KytosNApp class.
        Users shouldn't call this method directly.
        """
        pass

    @listen_to('kytos/of_core.v0x01.messages.in.ofpt_packet_in')
    def handle_packet_in(self, event):
        """Handle PacketIn Event.

        Install flows allowing communication between switch ports.

        Args:
            event (KytosPacketIn): Received Event
        """
        log.debug("PacketIn Received")

        packet_in = event.content['message']

        ethernet = Ethernet()
        ethernet.unpack(packet_in.data.value)

        # Ignore LLDP packets or packets not generated by table-miss flows
        if (ethernet.destination in settings.lldp_macs or
            packet_in.reason != PacketInReason.OFPR_NO_MATCH):
            return

        # Learn the port where the sender is connected
        in_port = packet_in.in_port.value
        switch = event.source.switch
        switch.update_mac_table(ethernet.source, in_port)

        ports = switch.where_is_mac(ethernet.destination)

        # Add a flow to the switch if the destination is known
        if ports:
            flow_mod = FlowMod()
            flow_mod.command = FlowModCommand.OFPFC_ADD
            flow_mod.match = Match()
            flow_mod.match.dl_src = ethernet.source.value
            flow_mod.match.dl_dst = ethernet.destination.value
            flow_mod.match.dl_type = ethernet.ether_type
            flow_mod.actions.append(ActionOutput(port=ports[0]))
            event_out = KytosEvent(name=('kytos/of_l2ls.messages.out.'
                                         'ofpt_flow_mod'),
                                   content={'destination': event.source,
                                            'message': flow_mod})
            self.controller.buffers.msg_out.put(event_out)

        # Send the packet to correct destination or flood it
        packet_out = PacketOut()
        packet_out.buffer_id = packet_in.buffer_id
        packet_out.in_port = packet_in.in_port
        packet_out.data = packet_in.data

        port = ports[0] if ports else Port.OFPP_FLOOD
        packet_out.actions.append(ActionOutput(port=port))
        event_out = KytosEvent(name=('kytos/of_l2ls.messages.out.'
                                     'ofpt_packet_out'),
                               content={'destination': event.source,
                                        'message': packet_out})

        self.controller.buffers.msg_out.put(event_out)

    def shutdown(self):
        """Too simple to have a shutdown procedure."""
        pass
