# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.19.0] - 2026-10-25

### Changed

- Keep every candidate's transcript and list the queue locally (#80)

## [5.18.2] - 2026-10-24

### Fixed

- Make ocr --output name the one requested format, or refuse several (#79)

## [5.18.1] - 2026-10-24

### Fixed

- Skip the quality gate for a winner outside the Latin script (#78)

## [5.18.0] - 2026-10-24

### Changed

- Article on measuring the Armenian fold release by release (#73)
- Bump transitive npm dependencies flagged by Dependabot (#74)
- Follow-up article on page orientation for Armenian (#75)
- Link Empire on Trial to the Armenian Institute project page (#76)
- Carry positioned spans out of the backends and measure their reading order (#77)

## [5.17.0] - 2026-10-16

### Added

- Add claude-haiku, the smaller model, as its own backend (#71)

### Changed

- Article on reading a page's orientation from its ink (#70)

## [5.16.0] - 2026-10-16

### Added

- Add further reading to the fold article

### Changed

- Drop the average bars from the research walkthrough
- Fold installation into a three-step tutorial
- Move the house rules to AGENTS.md for any coding agent
- Telling classical from reformed Armenian by one letter
- Open the orthography article with the reform's history
- Transliterate for display, fold for finding
- Open the fold article with Tumanyan's four spellings
- Show the fold catching Thoumanian, Hovannes and Ovanes
- Use an ALA-LC ambiguity the 2022 table still has
- Describe what changed in ISO 9984 and ISO 9985 in 2026
- Open articles with a real-world example and end with further reading
- Write a CSV manifest of each file, as a beta

## [5.15.0] - 2026-10-09

### Changed

- Stop ignoring cntx's workspace folder
- When your training set has read your test set
- Deploy the API reference from the release, after the publish job
- Move the user guide to Sphinx and stub the site reference page
- Auto-local is no longer the best local engine
- Score the two-letter եւ and the ligature և as one

## [5.14.1] - 2026-10-04

### Changed

- Bring CLAUDE.md and the skills up to date after the split
- Correct the corpus skill's re-fit sequence and [published]
- Drop the unused Read the Docs config
- Move the Omeka stack out to tetrak-omeka
- Publish each release to PyPI as tetrak

### Fixed

- Report the real version and the real distribution name
- Correct the remaining distribution-name references

## Earlier releases

Releases up to and including the version this repository's first commit is
tagged with were developed in a private repository, and their history is not
published.
