# Portable research release

The portable release lets readers inspect the
analysis before installing a research environment. It preserves the saved
development research status and every unresolved financial gate. Packaging does
not change the project's completion criteria or cure source discrepancies.

## Open the delivered work

Extract `output/releases/structured_credit_research.zip` into any local folder.
Open `structured-credit-research/START_HERE.html` in a browser. Its links open the
interactive dashboard, Excel model and two-page memo from the
extracted directory. Extract the whole archive rather than opening a single file
inside a ZIP viewer.

The dashboard embeds its scenario data, styles and JavaScript. It does not require
the author's machine, an active localhost server, Python, Node, a loan panel or an
internet connection. The external official-source links need internet access.
The workbook requires a compatible spreadsheet application; the delivered file
contains cached formula results. Native Excel interaction was not part of the
recorded artifact verification. Read the workbook's limitations before changing
inputs. Browser yield controls reprice the saved cash flows; changing borrower
assumptions requires a Python research rebuild.

If a managed browser blocks local HTML files, serve the extracted folder with a
standard Python installation:

```powershell
python -m http.server 8876 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8876/START_HERE.html` from the extracted
`structured-credit-research` directory.

## Verify or rebuild the package

Python 3.11+ and its standard library are sufficient. No artifact-authoring
runtime or third-party package is used to package the existing deliverables.

```powershell
python scripts/package_release.py
python scripts/package_release.py --verify output/releases/structured_credit_research.zip
```

The builder requires a matching successful results-generation record and the
version-bound artifact verification record. It checks the dashboard's embedded
JSON against the saved research results, the three delivered artifact hashes,
recorded model/build-script hashes, and every local HTML link. It rejects an
unexpected symlink or a changed deliverable before creating a release.

The ZIP includes `RELEASE_MANIFEST.json` with a SHA-256 and byte count for every
included file. The external `.zip.sha256` file identifies the complete archive.
The `--verify` command independently reads the ZIP, rejects duplicate or unsafe
entry paths, confirms its exact inventory and file hashes, and repeats the
version/link checks. This is an integrity check, not a signature proving who
authored the work. The adjacent `.zip.verification.json` records the package
check; saved financial verification remains in `output/artifact_verification.json`.

Source/model files, protocols, source manifests, extracted certificate evidence,
research outputs, documentation, unit tests and the small original SEC fixture
are included. Two small executed SEC document archives are explicitly included:
`data/raw/legal/d943115dex991.htm.gz` (sale/servicing agreement) and
`data/raw/legal/d943115dex41.htm.gz` (indenture). Their original and compressed
byte identities are verified against the frozen core source manifest. This lets
the separate conditional OC sensitivity reproduce without a source download:

```powershell
python scripts/analyze_oc_sensitivity.py --verify-only
python scripts/analyze_oc_sensitivity.py
```

The sensitivity is conditional research, keeps the unresolved $76.08 contractual
definition visible, and does not establish that the reported-dollar target is
legally authorized. All other bulk raw source archives, the approximately 1.19 GB SQLite panel,
dependency runtimes and ignored manual QA workspace are omitted. The manifest
distinguishes this saved-output delivery from a full raw-data replication.

## Reproduce analysis in a separate environment

For the small offline fixture, the included code and compressed SEC certificate
fixtures are sufficient:

```powershell
python scripts/run_research.py --output-dir output/bounded_fixture
python -m unittest discover -s tests -v
```

The entire test suite also requires the dependencies in `requirements.txt`.
Passing the fixture or tests does not validate the full loan panel or resolve the
public source exceptions.

Full model and source reproduction requires downloading the official files in
the included manifests, verifying their original and archived byte identities,
and reconstructing the excluded panel. Follow the main README and data
dictionary. Supply your own identifying SEC User-Agent; do not reuse the author's
contact identity. Source downloads total approximately 11.85 GB before gzip
compression. The supplemental reference inventory is separate. Acquisition
requires network access and can take substantial time.

The existing workbook builder uses `@oai/artifact-tool` through the Codex bundled
artifact runtime. That runtime is not distributed in this release. Readers
can inspect and recalculate the delivered Excel file without it; exact workbook
re-authoring requires access to that runtime. The Python HTML/PDF builder needs
the documented Python dependencies and matching saved research results, but no
raw panel solely to rebuild those two saved-output artifacts. The full artifact
verifier additionally requires manual review records from a fresh inspection;
those records are not inferred or manufactured from the shipped ZIP.
