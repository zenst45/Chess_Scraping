# ♟️ Chess Scraping

> A Python toolkit for scraping and serving chess game data and player information.

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)

---

## 📖 Overview

**Chess Scraping** is a lightweight Python project that collects chess games and player data from the web and exposes it through a local server. Whether you're building a chess analytics dashboard, training a machine learning model, or just exploring game statistics, this toolkit gives you an easy programmatic interface to real chess data.

---

## 📁 Project Structure

```
chess-scraping/
├── get_games.py     # Scrapes chess game data
├── get_players.py   # Scrapes player profiles and statistics
├── others.py        # Utility/helper functions
├── server.py        # Local server to expose scraped data via API
└── LICENSE
```

---

## 🚀 Getting Started

### Prerequisites

Make sure you have Python 3.x installed. Then install the required dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** Common dependencies for this type of project include `requests`, `beautifulsoup4`, and `flask`. Check the source files for the full list.

### Running the Server

```bash
python server.py
```

This will start a local server that exposes the scraped data through an API endpoint.

### Scraping Games

```bash
python get_games.py
```

### Scraping Players

```bash
python get_players.py
```

---

## 🔧 Modules

### `get_games.py`
Handles scraping of chess game records. Retrieves game metadata such as moves, results, openings, and player information.

### `get_players.py`
Fetches player profiles and statistics — ratings, win rates, game counts, and more.

### `others.py`
Contains shared utility functions and helpers used across the other modules (parsing, formatting, request handling, etc.).

### `server.py`
A lightweight local server that serves the collected data, making it easy to query programmatically or integrate with other tools.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

Made by [zenst45](https://github.com/zenst45)
