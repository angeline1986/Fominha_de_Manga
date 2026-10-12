"""Serialize all experimental L3 treatment workers in this server process."""
import threading

TREATMENT_LOCK = threading.Lock()
