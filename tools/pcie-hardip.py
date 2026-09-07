#!/usr/bin/env python3
"""Print the PCIe hard block's own view of the function, over the UART
(diagnostic image c1100_pcie_diag with the zhardip block; litex_server running).

    tools/pcie-hardip.py [--build ~/MiSTeX-ports/build/c1100_pcie_diag] [--clear]

Every field here is what PG213 says decides whether the integrated block
presents a memory request on CQ or answers it itself.
"""
import argparse, os, sys
sys.path.insert(0, os.path.expanduser("~/MiSTeX-ports/venv/lib/python3.12/site-packages"))
from litex import RemoteClient

LTSSM = {0x00: "Detect.Quiet", 0x01: "Detect.Active", 0x02: "Polling.Active", 0x03: "Polling.Compliance",
         0x04: "Polling.Configuration", 0x05: "Configuration.Linkwidth.Start", 0x06: "Configuration.Linkwidth.Accept",
         0x07: "Configuration.Lanenum.Accept", 0x08: "Configuration.Lanenum.Wait", 0x09: "Configuration.Complete",
         0x0A: "Configuration.Idle", 0x0B: "Recovery.RcvrLock", 0x0C: "Recovery.Speed", 0x0D: "Recovery.RcvrCfg",
         0x0E: "Recovery.Idle", 0x10: "L0", 0x11: "Rx_L0s.Entry", 0x12: "Rx_L0s.Idle", 0x13: "Rx_L0s.FTS",
         0x14: "Tx_L0s.Entry", 0x15: "Tx_L0s.Idle", 0x16: "Tx_L0s.FTS", 0x17: "L1.Entry", 0x18: "L1.Idle",
         0x19: "L2.Idle", 0x1A: "L2.TransmitWake", 0x20: "Disabled", 0x21: "Loopback_Entry_Master",
         0x22: "Loopback_Active_Master", 0x23: "Loopback_Exit_Master", 0x24: "Loopback_Entry_Slave",
         0x25: "Loopback_Active_Slave", 0x26: "Loopback_Exit_Slave", 0x27: "Hot_Reset", 0x28: "Recovery_Equalization_Phase0",
         0x29: "Recovery_Equalization_Phase1", 0x2A: "Recovery_Equalization_Phase2", 0x2B: "Recovery_Equalization_Phase3"}
PM = {0: "D0", 1: "D1", 2: "D2", 3: "D3hot"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", default=os.path.expanduser("~/MiSTeX-ports/build/c1100_pcie_diag"))
    ap.add_argument("--port", type=int, default=1234)
    ap.add_argument("--clear", action="store_true", help="clear the latched flags and counters first")
    a = ap.parse_args()
    wb = RemoteClient(csr_csv=os.path.join(a.build, "csr.csv"), port=a.port); wb.open()
    r = wb.regs
    if a.clear:
        r.zhardip_clear.write(1)
    fs = r.zhardip_function_status.read()
    print(f"function_status     0x{fs:04x}  PF0: IO_en={fs & 1} MEM_en={(fs >> 1) & 1} BUS_MASTER_en={(fs >> 2) & 1} INTx_dis={(fs >> 3) & 1}")
    ps = r.zhardip_function_power_state.read()
    print(f"function_power_state 0x{ps:03x}  PF0: {PM.get(ps & 7, ps & 7)}")
    lt = r.zhardip_ltssm_state.read()
    print(f"ltssm_state         0x{lt:02x}  {LTSSM.get(lt, '?')}")
    print(f"negotiated_width    {r.zhardip_negotiated_width.read()}  (0=x1 1=x2 2=x4 3=x8 4=x16)")
    print(f"current_speed       {r.zhardip_current_speed.read()}  (0=2.5 1=5 2=8 GT/s)")
    print(f"phy_link_status     {r.zhardip_phy_link_status.read()}  phy_link_down {r.zhardip_phy_link_down.read()}")
    print(f"flr_in_process      0x{r.zhardip_flr_in_process.read():x}")
    print(f"np_req_count        {r.zhardip_np_req_count.read()}   tfc_nph_av {r.zhardip_tfc_nph_av.read()} tfc_npd_av {r.zhardip_tfc_npd_av.read()} rq_tag_av {r.zhardip_rq_tag_av.read()}")
    print(f"rx_pm_state {r.zhardip_rx_pm_state.read()}  tx_pm_state {r.zhardip_tx_pm_state.read()}  rcb_status 0x{r.zhardip_rcb_status.read():x}")
    print(f"max_payload {r.zhardip_max_payload.read()} max_read_req {r.zhardip_max_read_req.read()} msi_enable 0x{r.zhardip_msi_enable.read():x}")
    print(f"local_error_out     0x{r.zhardip_local_error_out.read():02x}  local_error_valid seen {r.zhardip_local_error_valid_seen.read()}")
    print(f"err_cor seen {r.zhardip_err_cor_seen.read()}  err_nonfatal seen {r.zhardip_err_nonfatal_seen.read()}  err_fatal seen {r.zhardip_err_fatal_seen.read()}")
    print(f"hot_reset seen {r.zhardip_hot_reset_seen.read()}  power_state_change seen {r.zhardip_power_state_change_seen.read()}  pl_status_change seen {r.zhardip_pl_status_change_seen.read()}")
    print(f"messages received   {r.zhardip_msg_count.read()}  last type 0x{r.zhardip_msg_received_type.read():02x}  (msg_received seen {r.zhardip_msg_received_seen.read()})")
    print(f"CQ beats accepted, ever: {r.zhardip_cq_beats.read()}")
    print(f"scratch 0x{r.ctrl_scratch.read():08x}  bus_errors {r.ctrl_bus_errors.read()}")
    wb.close()


if __name__ == "__main__":
    main()
