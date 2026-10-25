# LureLab

 Phishing Awareness & Security Lab

Developer: sudopenmark

LureLab is a controlled security-awareness laboratory for demonstrating how
phishing-style landing pages, local HTTP services, and tunnel-based testing
work.

## Safety by design

LureLab intentionally does **not** store or transmit submitted passwords.
Simulation events record only metadata such as whether a username/password
field was populated.

Use the project only on systems, domains, and accounts you own or have
explicit authorization to test.

## Features

- Tkinter cybersecurity-themed GUI
- Custom landing-page generation
- Custom logo/background/color options
- Local HTTP simulation server
- Optional tunnel integration for authorized lab testing
- Simulation-event logging
- No credential storage

## Run

```bash
python3 LureLab.py
```

## Developer

sudopenmark
