"""Execute and validate the research notebook with the current Python interpreter."""
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / "notebooks/03_stress_model_calibration.ipynb"
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager()
    manager._kernel_spec = KernelSpec(
        argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
        display_name="Python 3", language="python")
    client = NotebookClient(notebook, km=manager, timeout=180,
                            resources={"metadata": {"path": str(root)}}, record_timing=False)
    client.execute()
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    count = sum(c.cell_type == "code" for c in notebook.cells)
    print(f"Notebook executed and validated: {count} code cells, no errors")


if __name__ == "__main__":
    main()
