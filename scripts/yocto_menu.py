#!/usr/bin/env python3
"""
Yocto Menu - A TUI for managing the Yocto workspace.
"""
import curses
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Callable, Optional

# Add scripts dir to path to import yocto_utils
SCRIPTS_DIR = Path(__file__).parent.resolve()
sys.path.append(str(SCRIPTS_DIR))

try:
    import yocto_utils
except ImportError:
    # Fallback if running standalone without yocto_utils nearby
    yocto_utils = None

class MenuItem:
    def __init__(self, label: str, action: Callable or str, description: str = ""):
        self.label = label
        self.action = action  # Can be a function or a shell command string
        self.description = description

class Menu:
    def __init__(self, title: str, items: List[MenuItem]):
        self.title = title
        self.items = items
        self.selected_idx = 0

class YoctoMenuApp:
    def __init__(self):
        self.workspace_root = self._find_workspace_root()
        self.stdscr = None
        self.running = True
        self.current_menu = None
        self.menu_stack = []
        
        # Build hierarchy
        self.main_menu = self._build_menus()
        self.current_menu = self.main_menu

    def _find_workspace_root(self) -> Path:
        """Find the workspace root (parent of scripts dir)."""
        return SCRIPTS_DIR.parent

    def _build_menus(self) -> Menu:
        """Define the menu structure."""
        
        # Build & Run Submenu
        build_menu = Menu("Build & Run", [
            MenuItem("Build Image", f"python3 {SCRIPTS_DIR}/build_recipe.py", "Build the default or last used image"),
            MenuItem("Run in QEMU", f"python3 {SCRIPTS_DIR}/run_qemu.py --interactive", "Run an image in QEMU (interactive selection)"),
            MenuItem("Build SDK", f"python3 {SCRIPTS_DIR}/manage_sdk.py --build --interactive", "Build the SDK for cross-development"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Projects Submenu
        project_menu = Menu("Project Management", [
            MenuItem("New Project", f"python3 {SCRIPTS_DIR}/new_project.py", "Create a new project"),
            MenuItem("Add Existing Project", f"python3 {SCRIPTS_DIR}/add_package.py", "Add an existing project to the workspace"),
            MenuItem("Live Edit Recipe", f"python3 {SCRIPTS_DIR}/live_edit.py", "Edit a recipe in the workspace"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])
        
        # Layers Submenu
        layer_menu = Menu("Layer Management", [
            MenuItem("New Layer", f"python3 {SCRIPTS_DIR}/layer_manager.py --new", "Create a new Yocto layer"),
            MenuItem("Sync Layers", f"python3 {SCRIPTS_DIR}/layer_manager.py", "Synchronize layer configurations"),
            MenuItem("Layer Info", f"python3 {SCRIPTS_DIR}/layer_manager.py --info --interactive", "View layer details and recipes"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Configuration Submenu
        config_menu = Menu("Configuration", [
            MenuItem("Machine Settings", f"python3 {SCRIPTS_DIR}/machine_manager.py", "Manage target machine configuration"),
            MenuItem("Optimize Workspace", f"python3 {SCRIPTS_DIR}/optimize_workspace.py", "Optimize local.conf for this host"),
            MenuItem("IDE Setup", f"python3 {SCRIPTS_DIR}/setup_ide.py", "Generate IDE configuration"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Analysis Submenu
        analysis_menu = Menu("Analysis & Health", [
            MenuItem("Workspace Health", f"python3 {SCRIPTS_DIR}/check_health.py", "Check workspace health status"),
            MenuItem("Check Layers", f"python3 {SCRIPTS_DIR}/check_layer.py", "Sanity check local layers"),
            MenuItem("Visualize Dependencies", self.prompt_dependency_viz, "Visualize project dependencies"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Main Menu
        main_items = [
            MenuItem("Build & Run >", lambda: self.enter_menu(build_menu), "Build images, SDKs, and run QEMU"),
            MenuItem("Projects >", lambda: self.enter_menu(project_menu), "Create and manage projects"),
            MenuItem("Layers >", lambda: self.enter_menu(layer_menu), "Manage Yocto layers"),
            MenuItem("Configuration >", lambda: self.enter_menu(config_menu), "Machine and workspace settings"),
            MenuItem("Analysis >", lambda: self.enter_menu(analysis_menu), "Health checks and dependency analysis"),
            MenuItem("Make Clean", f"python3 {SCRIPTS_DIR}/safe_cleanup.py", "Clean build artifacts"),
            MenuItem("Exit", self.exit_app, "Exit the menu")
        ]
        
        return Menu("Yocto Workspace Manager", main_items)

    def start(self):
        """Start the curses application."""
        curses.wrapper(self.main_loop)

    def main_loop(self, stdscr):
        """Main event loop."""
        self.stdscr = stdscr
        curses.curs_set(0) # Hide cursor
        curses.start_color()
        curses.use_default_colors()
        
        # Define colors
        curses.init_pair(1, -1, -1)   # Default
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN) # Selection
        curses.init_pair(3, curses.COLOR_CYAN, -1) # Header/Accent
        curses.init_pair(4, curses.COLOR_YELLOW, -1) # Warning/Info

        while self.running:
            self.draw_screen()
            key = self.stdscr.getch()
            self.handle_input(key)

    def draw_screen(self):
        """Draw the current menu state."""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()

        # Header
        title = f" {self.current_menu.title} "
        self.stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
        self.stdscr.addstr(1, 2, title)
        self.stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
        
        # Status Bar (Top Right)
        if yocto_utils:
            try:
                machine = yocto_utils.get_machine_from_config(self.workspace_root) or "Unknown"
                layer = yocto_utils.get_cached_layer(self.workspace_root) or "None"
                status_text = f"Machine: {machine} | Layer: {layer}"
                if len(status_text) + 4 < width:
                    self.stdscr.addstr(1, width - len(status_text) - 2, status_text, curses.color_pair(4))
            except Exception:
                pass

        # Border/Separator
        self.stdscr.hline(2, 2, curses.ACS_HLINE, width - 4)

        # Menu Items
        for idx, item in enumerate(self.current_menu.items):
            y = 4 + idx
            if y >= height - 3: # Check bounds
                break
                
            label = f" {item.label} "
            if idx == self.current_menu.selected_idx:
                self.stdscr.attron(curses.color_pair(2))
                self.stdscr.addstr(y, 4, f"{label:<{width-8}}") # Full width selection
                self.stdscr.attroff(curses.color_pair(2))
            else:
                self.stdscr.addstr(y, 4, label)

        # Footer (Description)
        description = self.current_menu.items[self.current_menu.selected_idx].description
        if description:
            self.stdscr.hline(height - 3, 2, curses.ACS_HLINE, width - 4)
            self.stdscr.addstr(height - 2, 4, description, curses.color_pair(4))

        self.stdscr.refresh()

    def handle_input(self, key):
        """Handle keyboard input."""
        if key == curses.KEY_UP:
            self.current_menu.selected_idx = max(0, self.current_menu.selected_idx - 1)
        elif key == curses.KEY_DOWN:
            self.current_menu.selected_idx = min(len(self.current_menu.items) - 1, self.current_menu.selected_idx + 1)
        elif key in [curses.KEY_ENTER, 10, 13]:
            self.execute_item()
        elif key == 27: # Python curses doesn't always map ESC well, but 27 is standard
            # Check if we should go back or exit
            # Non-blocking check for input sequence to differentiate ESC from arrow keys could go here
            # For simplicity, treating ESC as Back request
            if len(self.menu_stack) > 0:
                self.go_back()
            else:
                self.exit_app()
        elif key == ord('q') or key == ord('Q'):
             if len(self.menu_stack) > 0:
                self.go_back()
             else:
                self.exit_app()

    def execute_item(self):
        """Execute the currently selected item."""
        item = self.current_menu.items[self.current_menu.selected_idx]
        
        if callable(item.action):
            item.action()
        elif isinstance(item.action, str):
            self.run_shell_command(item.action)

    def run_shell_command(self, cmd: str):
        """Temporarily exit curses to run a shell command."""
        curses.def_prog_mode() # Save curses state
        curses.endwin()        # Restore terminal
        
        print(f"\nRunning: {cmd}\n" + "-"*40)
        try:
            # Check if command needs input/args that we haven't provided
            # Some commands might be interactive
            subprocess.run(cmd, shell=True, cwd=self.workspace_root)
        except Exception as e:
            print(f"Error executing command: {e}")
        
        print("\n" + "-"*40)
        input("Press Enter to return to menu...")
        
        curses.reset_prog_mode() # Restore curses state
        self.stdscr.refresh()

    def enter_menu(self, menu: Menu):
        """Navitgate into a submenu."""
        self.menu_stack.append(self.current_menu)
        self.current_menu = menu
        self.current_menu.selected_idx = 0

    def go_back(self):
        """Go back to the parent menu."""
        if self.menu_stack:
            self.current_menu = self.menu_stack.pop()
    
    def exit_app(self):
        """Stop the application."""
        self.running = False
        
    def prompt_dependency_viz(self):
        """Special handler for dependency visualization to ask for project name."""
        # We need to temporarily exit curses to get input and run the command
        curses.def_prog_mode()
        curses.endwin()
        
        try:
            project = input("Enter project name to visualize (e.g. talon): ").strip()
            if project:
                # Use python3 explicit execution
                cmd = f"python3 {SCRIPTS_DIR}/view_deps.py {project}"
                # We don't use run_shell_command here because we are already out of curses
                print(f"\nRunning: {cmd}\n" + "-"*40)
                try:
                    subprocess.run(cmd, shell=True, cwd=self.workspace_root)
                except Exception as e:
                    print(f"Error executing command: {e}")
                
                print("\n" + "-"*40)
                input("Press Enter to return to menu...")
            else:
                print("Cancelled.")
                time.sleep(1)
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

if __name__ == "__main__":
    try:
        app = YoctoMenuApp()
        app.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Ensure terminal is restored on crash
        if 'curses' in sys.modules:
            try:
                curses.endwin()
            except:
                pass
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
