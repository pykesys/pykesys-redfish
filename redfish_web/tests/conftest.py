import pytest
import django
from django.conf import settings


@pytest.fixture
def bmc_host(db):
    from hosts.models import BMCHost
    return BMCHost.objects.create(
        host="https://bmc.test",
        display_name="Test BMC",
        username="admin",
        password="password",
    )


@pytest.fixture
def snapshot(db, bmc_host):
    from inventory.models import InventorySnapshot
    return InventorySnapshot.objects.create(
        host=bmc_host,
        power_state="On",
        health="OK",
        model="PowerEdge R750",
        manufacturer="Dell",
        serial_number="ABC123",
        bios_version="2.1.0",
        total_memory_gib=256,
        processor_count=2,
        processor_model="Intel Xeon Gold 6338",
    )
