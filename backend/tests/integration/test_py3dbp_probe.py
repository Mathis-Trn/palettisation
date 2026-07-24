"""Sonde réelle de py3dbp==1.1.2 : documente la convention d'axes et de rotation_type
*effectivement* renvoyée par la bibliothèque installée, avant d'écrire l'adaptateur métier.

Ce test ne doit jamais être supprimé : il garantit que si la version de py3dbp change de
comportement, la suite le détecte immédiatement plutôt que de produire silencieusement des
coordonnées fausses dans l'adaptateur.
"""

from py3dbp import Bin, Item, Packer
from py3dbp.constants import RotationType


def test_probe_rotation_dimension_table() -> None:
    """Pour chaque rotation_type, get_dimension() renvoie [w', h', d'] en fonction des attributs
    d'origine (width, height, depth). On le vérifie avec 3 valeurs distinctes pour ne laisser
    aucune ambiguïté sur quel attribut d'origine finit sur quel axe."""
    item = Item("probe", width=100, height=200, depth=300, weight=1)
    observed: dict[int, list[float]] = {}
    for rt in RotationType.ALL:
        item.rotation_type = rt
        observed[rt] = item.get_dimension()

    # Table figée observée avec py3dbp 1.1.2 (width=100, height=200, depth=300) :
    expected = {
        RotationType.RT_WHD: [100, 200, 300],  # [w, h, d]           -> pas de rotation
        RotationType.RT_HWD: [200, 100, 300],  # [h, w, d]
        RotationType.RT_HDW: [200, 300, 100],  # [h, d, w]
        RotationType.RT_DHW: [300, 200, 100],  # [d, h, w]
        RotationType.RT_DWH: [300, 100, 200],  # [d, w, h]
        RotationType.RT_WDH: [100, 300, 200],  # [w, d, h]
    }
    assert observed == expected, observed


def test_probe_axis_index_meaning() -> None:
    """position/get_dimension index 0 = étendue le long de bin.width, 1 = bin.height,
    2 = bin.depth (confirmé en lisant Bin.put_item : pivot[0]+=w avance sur l'axe WIDTH,
    pivot[1]+=h sur HEIGHT, pivot[2]+=d sur DEPTH)."""
    packer = Packer()
    bin_ = Bin("pallet", width=1000, height=1000, depth=1000, max_weight=1000)
    packer.add_bin(bin_)
    # Deux items identiques : le second doit se placer à côté du premier le long de l'axe WIDTH
    # (axe 0), pas HEIGHT ni DEPTH, car c'est le premier axe testé par pack_to_bin.
    item_a = Item("a", width=100, height=50, depth=60, weight=1)
    item_b = Item("b", width=100, height=50, depth=60, weight=1)
    packer.add_item(item_a)
    packer.add_item(item_b)
    packer.pack()

    assert not bin_.unfitted_items
    positions = sorted(tuple(i.position) for i in bin_.items)
    assert positions == [(0, 0, 0), (100, 0, 0)], positions


def test_probe_unfitted_items_on_oversized() -> None:
    packer = Packer()
    bin_ = Bin("pallet", width=100, height=100, depth=100, max_weight=1000)
    packer.add_bin(bin_)
    oversized = Item("too-big", width=500, height=500, depth=500, weight=1)
    packer.add_item(oversized)
    packer.pack()

    assert bin_.items == []
    assert bin_.unfitted_items == [oversized]


def test_probe_weight_limit_rejects() -> None:
    packer = Packer()
    bin_ = Bin("pallet", width=100, height=100, depth=100, max_weight=5)
    packer.add_bin(bin_)
    heavy = Item("heavy", width=10, height=10, depth=10, weight=10)
    packer.add_item(heavy)
    packer.pack()

    assert bin_.items == []
    assert bin_.unfitted_items == [heavy]


def test_probe_single_bin_only_no_auto_multi_bin_distribution() -> None:
    """Packer.pack() sans distribute_items=True n'enlève pas les items déjà tentés sur un bin :
    avec plusieurs bins et distribute_items=False (défaut), CHAQUE bin retente TOUS les items
    (y compris ceux déjà placés ailleurs), donc l'adaptateur métier ne doit jamais réutiliser
    packer.items tel quel pour une boucle multi-palettes : il doit construire un Packer neuf par
    palette avec uniquement les instances restantes (ce que fait packing/adapter.py)."""
    packer = Packer()
    bin_a = Bin("a", width=50, height=50, depth=50, max_weight=1000)
    bin_b = Bin("b", width=50, height=50, depth=50, max_weight=1000)
    packer.add_bin(bin_a)
    packer.add_bin(bin_b)
    item = Item("x", width=10, height=10, depth=10, weight=1)
    packer.add_item(item)
    packer.pack(distribute_items=False)
    # Le même item est tenté sur bin_a ET bin_b (comportement réel à documenter, pas un défaut) :
    assert len(bin_a.items) + len(bin_a.unfitted_items) == 1
    assert len(bin_b.items) + len(bin_b.unfitted_items) == 1
