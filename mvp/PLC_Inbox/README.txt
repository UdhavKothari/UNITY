PLC_Inbox — drop-folder for PLC machine readings (fallback path)

Primary path: the server polls the PLC database directly every 10 seconds (no files).
This folder is the FALLBACK: if you export the PLC table to Excel/CSV, drop the file
here and the server will import it, then move it to done/ (or error/ on a problem).

One file per machine. Name the file with the machine id, e.g.:
    JET-01.xlsx     JIG-01.csv
so the server knows which machine the reading belongs to.
