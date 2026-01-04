import os
import sys
import platform

def probe_ci_environment():
    """Prints critical CI environment details for diagnostics."""
    print("=============================================")
    print(">>> CI Environment Diagnostic Probe (Python) <<<")
    print("=============================================")

    # --- User and Permissions ---
    print("\n--- User and Permissions ---")
    try:
        print(f"User: {os.getlogin()}")
    except Exception as e:
        print(f"Could not get login user: {e}")
    try:
        import pwd
        print(f"Effective User ID: {os.geteuid()} ({pwd.getpwuid(os.geteuid()).pw_name})")
    except Exception as e:
        print(f"Could not get effective user: {e}")

    # --- Directory Information ---
    print("\n--- Directory Information ---")
    try:
        cwd = os.getcwd()
        print(f"Working Directory: {cwd}")
        print("Directory Contents:")
        for item in os.listdir(cwd):
            print(f"  - {item}")
    except Exception as e:
        print(f"Could not get directory info: {e}")

    # --- System Information ---
    print("\n--- System Information ---")
    print(f"Platform: {platform.platform()}")
    print(f"System: {platform.system()}")
    print(f"Node: {platform.node()}")
    print(f"Release: {platform.release()}")
    print(f"Version: {platform.version()}")

    # --- Python Information ---
    print("\n--- Python Information ---")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version: {sys.version}")
    print("sys.path:")
    for p in sys.path:
        print(f"  - {p}")

    # --- Environment Variables ---
    print("\n--- Environment Variables ---")
    for key, value in sorted(os.environ.items()):
        print(f"{key}={value}")

    print("\n=============================================")
    print(">>> Probe Complete <<<")
    print("=============================================")

if __name__ == "__main__":
    probe_ci_environment()
