---
name: Test failure
about: Report a failing test in CI or local development
title: '[TEST] '
labels: 'bug, tests'
assignees: ''

---

**Which tests are failing?**
- [ ] Framework validation tests
- [ ] Index/main endpoint tests  
- [ ] Service management tests
- [ ] Credential management tests
- [ ] Authentication tests
- [ ] Share functionality tests
- [ ] All tests
- [ ] Other: _______________

**Environment**
- **OS**: [e.g. Ubuntu 22.04, macOS 13, Windows 11]
- **Python Version**: [e.g. 3.10.12]
- **Test Command**: [e.g. `make test`, `python run_tests.py`]
- **Environment**: [e.g. Local development, GitHub Actions, Docker]

**Error Output**
```
paste the full error output here
```

**Steps to reproduce locally**
1. [e.g. Clone the repo]
2. [e.g. Install dependencies with `pip install -r requirements-test.txt`]
3. [e.g. Run `make test`]

**Expected behavior**
Tests should pass without errors.

**Additional context**
- Is this happening consistently or intermittently?
- Did this work before? If so, what changed?
- Are you using any custom configuration?

**Dependencies**
Please run and paste the output of:
```bash
pip list | grep -E "(pytest|flask|peewee|troi)"
```
