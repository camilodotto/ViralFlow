#!/usr/bin/env python3

import argparse
import glob
import os
import sys


def write_entry_log(out_path, entries):
    with open(out_path, "w") as out_fl:
        header = "gnm,organism,status,bundle,download-link\n"
        out_fl.write(header)
        for data in entries:
            line = f"{data['gnm']},{data['organism']},{data['status']},{data['bundle']},{data['download-link']}\n"
            out_fl.write(line)


def user_error(args, message, details=None, entries=None):
    write_entry_log(args.output, entries or [])
    print("")
    print("ERROR: snpEff database is not ready for this ViralFlow run.")
    print("")
    print(message)
    print("")
    print(f"Virus parameter: {args.virus}")
    print(f"Reference genome code: {args.genome_code}")
    if details:
        print("")
        for detail in details:
            print(detail)
    print("")
    print("Before running ViralFlow with runSnpEff=true, add or download this snpEff database.")
    print("For custom viruses, use the ViralFlow snpEff database customization step before starting the pipeline.")
    sys.exit(1)


def find_snpeff_data_dirs():
    snpeff_roots = []
    for pattern in [
        "/opt/conda/share/snpeff-5.0-*",
        "/opt/conda/share/snpeff",
        "/usr/local/bin/mm/share/snpeff-5.0-*",
        "/usr/local/bin/mm/share/snpeff",
    ]:
        snpeff_roots.extend(glob.glob(pattern))

    data_dirs = []
    for root in sorted(set(snpeff_roots)):
        data_dir = os.path.join(root, "data")
        if os.path.isdir(data_dir):
            data_dirs.append(data_dir)
    return data_dirs


def is_database_installed(genome_code):
    data_dirs = find_snpeff_data_dirs()
    for data_dir in data_dirs:
        if os.path.isdir(os.path.join(data_dir, genome_code)):
            return True, data_dirs
    return False, data_dirs


def parse_catalog(catalog_path, genome_code):
    entries = []
    with open(catalog_path, "r") as srch_fl:
        for line in srch_fl:
            d_line = line.replace(" ", "").split("\t")
            if len(d_line) < 5:
                continue
            entry = {
                "gnm": d_line[0],
                "organism": d_line[1],
                "status": d_line[2],
                "bundle": d_line[3],
                "download-link": d_line[4],
            }

            if genome_code in entry["gnm"]:
                entries.append(entry)
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Check whether the requested snpEff database is available and installed."
    )
    parser.add_argument("--genome-code", required=True)
    parser.add_argument("--virus", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--published-output", required=True)
    args = parser.parse_args()

    entries = parse_catalog(args.catalog, args.genome_code)
    n_founds = len(entries)

    if n_founds == 0:
        user_error(
            args,
            f"The reference genome '{args.genome_code}' was not found in the snpEff database catalog.",
            [
                f"Catalog file checked: {args.catalog}",
                "Check whether the reference genome code is correct or prepare a custom snpEff database entry.",
            ],
        )

    if n_founds > 1:
        user_error(
            args,
            f"More than one snpEff catalog entry matched reference genome '{args.genome_code}'.",
            [
                f"Check the matching entries in: {args.published_output}",
                "Use a more specific reference genome code before running snpEff annotation.",
            ],
            entries=entries,
        )

    write_entry_log(args.output, entries)

    installed, checked_data_dirs = is_database_installed(args.genome_code)
    if not installed:
        details = [
            "The genome code exists in the snpEff catalog, but the database is not installed in the container.",
            "ViralFlow will not let snpEff download databases during the pipeline execution.",
        ]
        if checked_data_dirs:
            details.append("Checked snpEff data directories:")
            details.extend([f"  - {data_dir}" for data_dir in checked_data_dirs])
        else:
            details.append("No snpEff data directory was found inside the container.")

        user_error(
            args,
            f"The snpEff database for '{args.genome_code}' is not installed in the snpEff container.",
            details,
            entries=entries,
        )


if __name__ == "__main__":
    main()
