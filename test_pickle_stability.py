import os
import subprocess
import sys
import pickle
import unittest
import hashlib
import itertools
import math
import platform
import json


FIXED_HASH_SEED = "0"
PICKLE_PROTOCOL = 0


def ensure_fixed_hash_seed():
    if os.environ.get("PYTHONHASHSEED") == FIXED_HASH_SEED:
        return

    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = FIXED_HASH_SEED
    completed = subprocess.run([sys.executable] + sys.argv, env=environment)
    sys.exit(completed.returncode)


def pickle_bytes(obj):
    return pickle.dumps(obj, protocol=PICKLE_PROTOCOL)


def hash_pickle(data):
    return hashlib.sha256(data).hexdigest()


def pickle_and_hash(obj):
    data = pickle_bytes(obj)
    return hash_pickle(data)


class SimpleItem:
    def __init__(self, name, count):
        self.name = name
        self.count = count

    def __eq__(self, other):
        return (
            isinstance(other, SimpleItem)
            and self.name == other.name
            and self.count == other.count
        )

    def __repr__(self):
        return "SimpleItem({}, {})".format(self.name, self.count)


def make_recursive_list():
    values = []
    values.append(values)
    return values


def make_shared_list():
    shared = ["same list"]
    return [shared, shared]


def get_test_objects():
    return [
        ("int", 42),
        ("string", "hello pickle"),
        ("float", 3.14),
        ("bool_true", True),
        ("bool_false", False),
        ("none", None),
        ("list", [1, 2, 3, "four"]),
        ("empty_list", []),
        ("tuple", ("a", "b", 10, False)),
        ("empty_tuple", ()),
        ("dictionary", {"name": "Adam", "age": 36, "active": True}),
        ("dictionary_with_list", {"numbers": [1, 2, 3], "empty": None}),
        ("empty_dictionary", {}),
        ("set_numbers", {1, 2, 3}),
        ("set_strings", {"red", "green", "blue"}),
        ("empty_set", set()),
        ("frozenset", frozenset([10, 20, 30])),
        ("empty_frozenset", frozenset()),
        ("nested", {
            "users": [
                {"name": "Adam", "scores": (10, 20, 30)},
                {"name": "Bertil", "scores": (7, 8, 9)},
            ],
            "flags": {"tested", "stable"},
            "meta": {"version": 1, "enabled": True},
        }),
        ("float_addition", 0.1 + 0.2),
        ("float_inf", float("inf")),
        ("float_negative_inf", float("-inf")),
        ("float_nan", float("nan")),
        ("recursive_list", make_recursive_list()),
        ("shared_references", make_shared_list()),
        ("custom_class", SimpleItem("example", 3)),
    ]


def round_trip_ok(name, original, loaded):
    if name == "float_nan":
        return math.isnan(loaded)

    if name == "recursive_list":
        return loaded[0] is loaded

    if name == "shared_references":
        return loaded[0] == ["same list"] and loaded[0] is loaded[1]

    return original == loaded


def print_environment_info():
    print("Python version:", sys.version)
    print("Platform:", platform.platform())
    print("Pickle protocol:", PICKLE_PROTOCOL)


def safe_name(text): # Makes sure filename is safe (replaces the dots in python versions with underscores)
    result = ""

    for char in text:
        if char.isalnum() or char in ("_", "-"):
            result += char
        else:
            result += "_"

    return result


def result_file_name():
    parts = [
        platform.python_version(),
        platform.system(),
    ]
    return "_".join(safe_name(part) for part in parts) + ".json"


def make_result_data():
    data = {
        "environment": {
            "python_version": sys.version,
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
        },
        "cases": [],
    }

    for name, obj in get_test_objects():
        pickle_data = pickle_bytes(obj)
        loaded = pickle.loads(pickle_data)

        case = {
            "name": name,
            "sha256": hash_pickle(pickle_data),
            "round_trip_ok": round_trip_ok(name, obj, loaded),
        }

        data["cases"].append(case)

    return data


def save_result_file():
    file_name = result_file_name()

    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(make_result_data(), file, indent=2, sort_keys=True)

    return file_name


def load_result_file(file_name):
    with open(file_name, "r", encoding="utf-8") as file:
        return json.load(file)


def get_hashes(result_data):
    return {
        case["name"]: case["sha256"]
        for case in result_data["cases"]
    }


def get_case_details(result_data):
    return {
        case["name"]: case
        for case in result_data["cases"]
    }


def environment_label(file_name, result_data):
    environment = result_data["environment"]
    python_version = environment.get("python_version", "unknown").split()[0]
    implementation = environment.get("python_implementation", "Python")
    system = environment.get("system", "unknown OS")

    return "{}: {} {} on {}".format(
        file_name,
        implementation,
        python_version,
        system,
    )


def compare_hash_maps(first_hashes, second_hashes):
    common_keys = sorted(set(first_hashes) & set(second_hashes))

    same = 0
    different = []

    for key in common_keys:
        if first_hashes[key] == second_hashes[key]:
            same += 1
        else:
            different.append(key)

    return common_keys, same, different


def compare_all_files(file_names):
    loaded = [(file_name, load_result_file(file_name)) for file_name in file_names]
    hashes_by_file = {
        file_name: get_hashes(result_data)
        for file_name, result_data in loaded
    }
    details_by_file = {
        file_name: get_case_details(result_data)
        for file_name, result_data in loaded
    }

    print("Environments:")
    for file_name, result_data in loaded:
        print("- " + environment_label(file_name, result_data))

    print()
    print("Pairwise summary:")
    for first_file, second_file in itertools.combinations(file_names, 2):
        common_keys, same, different = compare_hash_maps(
            hashes_by_file[first_file],
            hashes_by_file[second_file],
        )
        case_summary = "none"

        if different:
            case_summary = ", ".join(different)

        print(
            "- {} vs {}: {}/{} same, {} different ({})".format(
                first_file,
                second_file,
                same,
                len(common_keys),
                len(different),
                case_summary,
            )
        )

    all_keys = sorted(set().union(*(set(hashes) for hashes in hashes_by_file.values())))
    varying_keys = []
    missing_keys = []
    failed_round_trips = []

    for key in all_keys:
        present_hashes = {
            file_name: hashes_by_file[file_name][key]
            for file_name in file_names
            if key in hashes_by_file[file_name]
        }

        if len(present_hashes) != len(file_names):
            missing_keys.append(key)

        if len(set(present_hashes.values())) > 1:
            varying_keys.append(key)

        for file_name in file_names:
            details = details_by_file[file_name].get(key)
            if details is not None and not details.get("round_trip_ok", False):
                failed_round_trips.append((file_name, key))

    print()
    print("Varying cases:", len(varying_keys))

    for name in varying_keys:
        print("- " + name)
        grouped = {}

        for file_name in file_names:
            details = details_by_file[file_name].get(name)
            if details is None:
                grouped.setdefault("missing", []).append(file_name)
                continue

            summary = "sha256 {}".format(details["sha256"][:12])
            grouped.setdefault(summary, []).append(file_name)

        for summary, matching_files in sorted(grouped.items()):
            print("  {}: {}".format(summary, ", ".join(matching_files)))

    if missing_keys:
        print()
        print("Missing cases:", len(missing_keys))
        for name in missing_keys:
            print("- " + name)

    if failed_round_trips:
        print()
        print("Round-trip failures:")
        for file_name, name in failed_round_trips:
            print("- {}: {}".format(file_name, name))


class TestPickleStability(unittest.TestCase):
    def check_stable(self, obj):
        first_hash = pickle_and_hash(obj)

        for _ in range(5):
            new_hash = pickle_and_hash(obj)
            self.assertEqual(first_hash, new_hash)

    def test_objects(self):
        for name, obj in get_test_objects():
            with self.subTest(name=name):
                self.check_stable(obj)

                pickle_data = pickle_bytes(obj)
                loaded = pickle.loads(pickle_data)
                self.assertTrue(round_trip_ok(name, obj, loaded))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--compare-all":
        if len(sys.argv) < 4:
            print("Usage: python test_pickle_stability.py --compare-all file1 file2 [file3 ...]")
            sys.exit(1)

        compare_all_files(sys.argv[2:])
        sys.exit(0)

    ensure_fixed_hash_seed()

    print_environment_info()
    saved_file = save_result_file()
    print("Saved comparison results:", saved_file)
    unittest.main()
