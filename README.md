🤖 Telegram ModBot — Advanced Community ModeratorA versatile Python bot designed for automated moderation and community management, built using the Aiogram 3.x framework and Supabase (PostgreSQL).📋 Project OverviewTelegram ModBot is engineered for structured communities and channels requiring strict discipline and efficient organization. It provides 24/7 moderation, tracks member activity, and streamlines the process of organizing polls and events.Key FeaturesCategoryFunctionMechanismModerationAnti-Spam / Anti-AggressionAutomatically deletes messages containing links, advertisements, or forbidden keywords (managed via Supabase).SanctionsWarning (Warn) SystemMaintains a violation counter in Supabase. Triggers an automatic ban after 3 warnings.AdministrationWarning ManagementCommands like /unwarn (to revoke a warning) and /reload (to update the keyword cache) are available to admins.OrganizationEvent CreationThe /event command allows admins to create non-anonymous polls, crucial for tracking quorums and RSVPs.EngagementWelcome MessageAutomatically greets new members and reminds them about the Community Rules.ArchitectureActivity TrackingMiddleware records the last active timestamp of each user (foundation for future inactivity cleanup).🛠️ Technology Stack & ArchitectureLanguage: Python 3.10+Framework: Aiogram v3.x (Asynchronous)Database: Supabase (PostgreSQL)Configuration: python-dotenv, pydantic-settingsData Layer: Repository Pattern (db_client.py) for easy database switching.🚀 Getting Started1. PrerequisitesAn active Supabase account and a configured database (see "Database Setup" below).Your bot token from @BotFather on Telegram.Python 3.10+ installed.2. Clone the RepositoryBashgit clone https://github.com/YourUsername/telegram-modbot.git
cd telegram-modbot 3. Install DependenciesIt is highly recommended to use a virtual environment.Bash# Create and activate venv
python -m venv venv
source venv/bin/activate # macOS/Linux

# Install libraries

pip install -r requirements.txt 4. Configure the .env FileCreate a file named .env in the project root and fill it with your secret credentials:Фрагмент кода# --- Telegram API ---
BOT_TOKEN=YOUR_BOT_TOKEN_FROM_BOTFATHER

# --- Supabase API ---

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key

# --- Administrator Settings ---

# A comma-separated list of Admin User IDs (get your ID from @userinfobot)

ADMIN_IDS=12345678,87654321
🐘 Database Setup (Supabase)Connect to your Supabase project, navigate to the SQL Editor, and execute the following script to create the necessary tables:SQL-- Table for users (tracking activity and warnings)
CREATE TABLE public.users (
user_id BIGINT PRIMARY KEY,
username TEXT,
full_name TEXT,
warning_count INT DEFAULT 0,
last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for forbidden keywords (for moderation)
CREATE TABLE public.bad_words (
id SERIAL PRIMARY KEY,
word TEXT NOT NULL
);

-- Insert initial keywords for testing
INSERT INTO public.bad_words (word) VALUES ('spam'), ('casino'), ('buy');
⚠️ Important: Management of the forbidden keyword list (bad_words) should be done via the Supabase Table Editor or SQL queries. After making changes, you must use the /reload command in a private chat with the bot.⚙️ Running and AutonomyLocal Run (For Testing Only)Bashpython main.py
Autonomous Deployment (Recommended for 24/7)To ensure your bot runs continuously and automatically recovers from crashes, you must deploy it on a remote server or hosting platform using a process manager.Recommended Deployment Methods:PaaS (Platform as a Service): Use Render.com or Railway.app. They automatically pull your code from the Git repository and handle process management.VPS (Virtual Private Server): Use a process manager like Supervisor or Systemd to ensure the python main.py command is always running in the background.🔒 Commands and SecurityCommandLocationAccessDescription/reloadPrivate Chat with BotAdministratorsUpdates the keyword cache from the DB without restarting the bot. (Secured by IsProtectedAdmin)./event [name]Group ChatAdministratorsCreates a non-anonymous poll for planning events./unwarnReply to message in GroupAdministratorsRevokes one warning from the user whose message is being replied to.Admin Command Security PrincipleCritical commands like /reload are protected by the IsProtectedAdmin() filter. This filter only allows execution if:The user is an administrator (by ID).The command is sent in a private chat with the bot, preventing accidental or malicious invocation in public groups.🤝 Contribution and SupportSuggestions and pull requests are welcome! If you plan to add new substantial features (like the scheduled inactivity cleanup module), please open an Issue first to discuss the implementation details.
