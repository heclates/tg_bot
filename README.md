# 🤖 Telegram ModBot — Advanced Community Moderator

A versatile Python bot designed for automated moderation and community management, built using Aiogram 3.x and Supabase (PostgreSQL).

## Project Overview

Telegram ModBot is engineered for structured communities and channels requiring strict discipline and efficient organization. It provides 24/7 moderation, tracks member activity, and streamlines polls and event management.

### Key Features

| Category       | Function                    | Mechanism                                                                                                      |
| -------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Moderation     | Anti-Spam / Anti-Aggression | Automatically deletes messages containing links, advertisements, or forbidden keywords (managed via Supabase). |
| Sanctions      | Warning (Warn) System       | Maintains a violation counter in Supabase. Triggers an automatic ban after 3 warnings.                         |
| Administration | Warning Management          | Commands like `/unwarn` (revoke warning) and `/reload` (update keyword cache) for admins.                      |
| Organization   | Event Creation              | `/event` command allows admins to create non-anonymous polls, tracking quorums and RSVPs.                      |
| Engagement     | Welcome Message             | Automatically greets new members and reminds them about Community Rules.                                       |
| Architecture   | Activity Tracking           | Middleware records the last active timestamp of each user (foundation for future inactivity cleanup).          |

## Technology Stack & Architecture

- Language: Python 3.10+
- Framework: Aiogram v3.x (Asynchronous)
- Database: Supabase (PostgreSQL)
- Configuration: python-dotenv, pydantic-settings
- Data Layer: Repository Pattern (db_client.py) for easy database switching

## Getting Started

### Prerequisites

- Active Supabase account with a configured database
- Telegram bot token from @BotFather
- Python 3.10+ installed

### Clone the Repository

git clone https://github.com/YourUsername/telegram-modbot.git
cd telegram-modbot

Install Dependencies

# Create and activate virtual environment

python -m venv venv
source venv/bin/activate # macOS/Linux

# Windows: venv\Scripts\activate

# Install libraries

pip install -r requirements.txt

Configure the .env File

Create a .env file in the project root:

# Telegram API

BOT_TOKEN=YOUR_BOT_TOKEN_FROM_BOTFATHER

# Supabase API

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key

# Administrator Settings

ADMIN_IDS=12345678,87654321

Database Setup (Supabase)

Connect to Supabase → SQL Editor → execute:
CREATE TABLE public.users (
user_id BIGINT PRIMARY KEY,
username TEXT,
full_name TEXT,
warning_count INT DEFAULT 0,
last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.bad_words (
id SERIAL PRIMARY KEY,
word TEXT NOT NULL
);

INSERT INTO public.bad_words (word) VALUES ('spam'), ('casino'), ('buy');
Note: Manage bad_words via Supabase Table Editor or SQL queries. After changes, run /reload in a private chat with the bot.

Running the Bot
Local Run (Testing)

    python main.py

Autonomous Deployment (24/7)

PaaS: Render.com, Railway.app (automatic deployment and process management)

VPS: Use Supervisor or Systemd to keep python main.py running continuously

Commands and Security
| Command | Location | Access | Description |
| --------------- | ---------------- | ------ | ------------------------------------------------ |
| `/reload` | Private Chat | Admins | Updates keyword cache without restarting the bot |
| `/event [name]` | Group Chat | Admins | Creates a non-anonymous poll for events |
| `/unwarn` | Reply to message | Admins | Revokes one warning from the replied user |

Admin Security Principle: Commands like /reload only run if:

    1. User is an admin by ID

    2. Command is sent in a private chat with the bot

Contribution & Support

Suggestions and pull requests are welcome. For major feature additions, open an Issue first to discuss details.
