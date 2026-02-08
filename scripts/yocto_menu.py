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
            MenuItem("Select Default Image", self.action_select_image, "Select the default image for build/run"),
            MenuItem("Build Image", f"python3 {SCRIPTS_DIR}/build_recipe.py", "Build the default or last used image"),
            MenuItem("Run in QEMU", f"python3 {SCRIPTS_DIR}/run_qemu.py --interactive", "Run an image in QEMU (interactive selection)"),
            MenuItem("Build SDK", f"python3 {SCRIPTS_DIR}/manage_sdk.py --build --interactive", "Build the SDK for cross-development"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Projects Submenu
        project_menu = Menu("Project Management", [
            MenuItem("New Project", self.action_new_project, "Create a new project"),
            MenuItem("Add Existing Project", self.action_add_project, "Add an existing project to the workspace"),
            MenuItem("Live Edit Recipe", self.action_live_edit, "Edit a recipe in the workspace"),
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
            MenuItem("Select Machine", self.action_select_machine, "Switch target machine"),
            MenuItem("Search Machine", self.action_search_machine, "Search for machines in Layer Index"),
            MenuItem("Get Machine", self.action_get_machine, "Fetch and install a machine's layer"),
            MenuItem("Manage Fragments", self.action_manage_fragments, "Enable/Disable configuration fragments"),
            MenuItem("Machine Settings", f"python3 {SCRIPTS_DIR}/machine_manager.py", "Manage target machine configuration"),
            MenuItem("Optimize Workspace", f"python3 {SCRIPTS_DIR}/optimize_workspace.py", "Optimize local.conf for this host"),
            MenuItem("IDE Setup", f"python3 {SCRIPTS_DIR}/setup_ide.py", "Generate IDE configuration"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Analysis Submenu
        analysis_menu = Menu("Analysis & Health", [
            MenuItem("Workspace Health", f"python3 {SCRIPTS_DIR}/check_health.py", "Check workspace health status"),
            MenuItem("Check Layers", f"python3 {SCRIPTS_DIR}/check_layer.py", "Sanity check local layers"),
            MenuItem("Search Recipe", self.action_search_recipe, "Search for recipes in Layer Index"),
            MenuItem("Get Recipe", self.action_get_recipe, "Fetch and install a recipe"),
            MenuItem("Visualize Dependencies", self.prompt_dependency_viz, "Visualize project dependencies"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Main Menu
        main_items = [
            MenuItem("Build & Run >", lambda: self.enter_menu(build_menu), "Build images, SDKs, and run QEMU"),
            MenuItem("Projects >", lambda: self.enter_menu(project_menu), "Create and manage projects"),
            MenuItem("Layers >", lambda: self.enter_menu(layer_menu), "Manage Yocto layers"),
            MenuItem("Configuration >", lambda: self.enter_menu(config_menu), "Machine and workspace settings"),
            MenuItem("Manage Image Packages >", self.action_manage_packages, "Add/Remove packages from image"),
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
                image = yocto_utils.get_cached_image(self.workspace_root) or "None"
                status_text = f"Machine: {machine} | Layer: {layer} | Image: {image}"
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
        self._run_command_impl(cmd)
        curses.reset_prog_mode() # Restore curses state
        self.stdscr.refresh()

    def _run_command_impl(self, cmd: str):
        """Run command assuming we are already in shell mode."""
        print(f"\nRunning: {cmd}\n" + "-"*40)
        try:
            # Check if command needs input/args that we haven't provided
            # Some commands might be interactive
            subprocess.run(cmd, shell=True, cwd=self.workspace_root)
        except Exception as e:
            print(f"Error executing command: {e}")
        
        print("\n" + "-"*40)
        input("Press Enter to return to menu...")

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
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def show_selection_menu(self, title: str, options: List[str], on_select: Callable[[str], None]):
        """Generic selection menu."""
        if not options:
            return

        # Create a temporary selection menu
        items = [MenuItem(opt, lambda opt=opt: self._handle_selection(opt, on_select), "") for opt in options]
        items.append(MenuItem("Cancel", self.go_back, "Cancel selection"))
        
        selection_menu = Menu(title, items)
        self.enter_menu(selection_menu)

    def _handle_selection(self, value: str, callback: Callable[[str], None]):
        """Handle selection and return to previous menu."""
        callback(value)
        self.go_back()

    def action_select_machine(self):
        """Show machine selection menu."""
        if not yocto_utils:
            return
            
        machines_dict = yocto_utils.get_available_machines(self.workspace_root)
        options = []
        
        # Add custom machines first
        if machines_dict.get('custom'):
            options.extend(machines_dict['custom'])
            
        # Add common Poky machines
        if machines_dict.get('poky'):
             # Limit to common ones to avoid clutter if list is huge
            options.extend(machines_dict['poky'])
            
        self.show_selection_menu("Select Target Machine", options, self._set_machine)

    def _set_machine(self, machine: str):
        """Callback to set the machine."""
        cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py {machine}"
        self.run_shell_command(cmd)

    def action_select_image(self):
        """Show image selection menu."""
        if not yocto_utils:
            return
            
        # Get built images
        images_list = yocto_utils.find_built_images(self.workspace_root)
        if not images_list:
            # Fallback to finding recipes if no images built
            try:
                layer = yocto_utils.find_custom_layer(self.workspace_root) # Get first custom layer
                recipes = yocto_utils.find_image_recipes(layer)
                options = recipes
            except:
                options = []
        else:
            options = sorted(list(set(img['name'] for img in images_list)))
            
        if not options:
            self.run_shell_command("echo 'No built images or image recipes found.'")
            return

        self.show_selection_menu("Select Default Image", options, self._set_image)

    def _set_image(self, image: str):
        """Callback to set the cached image."""
        yocto_utils.set_cached_image(self.workspace_root, image)
        # Show a quick confirmation (simulated since we are in curses)
        # Actually run_shell_command clears screen, so let's just use that to confirm
        self.run_shell_command(f"echo 'Selected image: {image}'")

    def action_search_machine(self):
        """Search for a machine."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            term = input("Enter search term: ").strip()
            if term:
                # Use subcommand syntax
                cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py search {term}"
                self._run_command_impl(cmd)
            else:
                self._run_command_impl("echo 'Cancelled.'")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_get_machine(self):
        """Get (install) a machine."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            name = input("Enter machine name to install: ").strip()
            if name:
                # Use subcommand syntax
                cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py get {name}"
                self._run_command_impl(cmd)
            else:
                self._run_command_impl("echo 'Cancelled.'")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_manage_fragments(self):
        """Submenu for fragment management."""
        options = [
            ("List Active Fragments", self.action_list_fragments),
            ("List Available Fragments", self.action_list_available_fragments),
            ("Enable Fragment", self.action_enable_fragment),
            ("Disable Fragment", self.action_disable_fragment)
        ]
        
        while True:
            # We construct a submenu loop here
            # Ideally proper submenu implementation, but for now just show a selection
            # Reuse show_selection_menu? logic or just loop
            
            # Simplified: Use a specific submenu method if I had one, 
            # OR just list them.
            
            # Let's map it to indices
            items = [opt[0] for opt in options]
            
            # Small hack: verify "Back" breaks loop
            # We can use simple input loop or use existing menu structure logic?
            # Existing logic is screen-based.
            # Let's just create a dynamic menu handling here because architecture allows it.
            
            # But wait, self.show_selection_menu expects a callback.
            # Let's use that.
            
            self.show_selection_menu("Fragment Management", items, self._handle_fragment_menu)
            break # show_selection_menu is blocking-ish in its own loop but returns result to callback

    def _handle_fragment_menu(self, selection):
        if selection == "List Active Fragments":
            self.action_list_fragments()
        elif selection == "List Available Fragments":
            self.action_list_available_fragments()
        elif selection == "Enable Fragment":
            self.action_enable_fragment()
        elif selection == "Disable Fragment":
            self.action_disable_fragment()
        # Back does nothing, just return

    def action_list_fragments(self):
        self.run_shell_command(f"python3 {SCRIPTS_DIR}/config_manager.py list")

    def action_list_available_fragments(self):
        self.run_shell_command(f"python3 {SCRIPTS_DIR}/config_manager.py list-available")

    def action_enable_fragment(self):
        curses.def_prog_mode()
        curses.endwin()
        try:
            val = input("Enter fragment to enable (e.g. machine/raspberrypi4): ").strip()
            if val:
                self._run_command_impl(f"python3 {SCRIPTS_DIR}/config_manager.py enable {val}")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_disable_fragment(self):
        # Could retrieve list first and make selection, for now simple input
        # Or better: parse list and show selection?
        # Let's try to be fancy: get list, show menu for disable
        
        # We need a way to get list programmatically. config_manager output parsing?
        curses.def_prog_mode()
        curses.endwin()
        try:
             # Run list to show user
             os.system(f"python3 {SCRIPTS_DIR}/config_manager.py list")
             val = input("\nEnter fragment to disable (or Enter to cancel): ").strip()
             if val:
                 self._run_command_impl(f"python3 {SCRIPTS_DIR}/config_manager.py disable {val}")
        finally:
             curses.reset_prog_mode()
             self.stdscr.refresh()

    # Image Package Management Actions
    def action_manage_packages(self):
        """Submenu for image package management."""
        options = [
            ("List Installed Packages", self.action_list_packages),
            ("Add Package", self.action_add_package),
            ("Remove Package", self.action_remove_package),
            ("Refresh Workspace", self.refresh_image_wrapper)
        ]
        items = [opt[0] for opt in options]
        self.show_selection_menu("Manage Image Packages", items, self._handle_pkg_menu)

    def _handle_pkg_menu(self, selection):
        if selection == "List Installed Packages":
            self.action_list_packages()
        elif selection == "Add Package":
            self.action_add_package()
        elif selection == "Remove Package":
             self.action_remove_package()
        elif selection == "Refresh Workspace":
             self.refresh_image_wrapper()

    def refresh_image_wrapper(self):
         self.run_shell_command(f"python3 {SCRIPTS_DIR}/update_image.py refresh")

    def action_list_packages(self):
        self.run_shell_command(f"python3 {SCRIPTS_DIR}/update_image.py list")

    def action_add_package(self):
        # Could show available list, but it might be huge.
        # Let's prompt for search term first?
        curses.def_prog_mode()
        curses.endwin()
        try:
            print("\n  Tip: You can search for packages or enter name directly.")
            term = input("  Enter package name (or part of name to search): ").strip()
            if term:
                # Run available with filter
                os.system(f"python3 {SCRIPTS_DIR}/update_image.py available {term}")
                print("\n")
                pkg = input("  Enter exact package name to ADD (or Enter to cancel): ").strip()
                if pkg:
                    self._run_command_impl(f"python3 {SCRIPTS_DIR}/update_image.py add {pkg}")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_remove_package(self):
        curses.def_prog_mode()
        curses.endwin()
        try:
            # Show list first
            os.system(f"python3 {SCRIPTS_DIR}/update_image.py list")
            print("\n")
            pkg = input("  Enter package name to REMOVE (or Enter to cancel): ").strip()
            if pkg:
                self._run_command_impl(f"python3 {SCRIPTS_DIR}/update_image.py remove {pkg}")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_search_recipe(self):
        """Search for a recipe in the Layer Index."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            term = input("Enter recipe name to search: ").strip()
            if term:
                self._run_command_impl(f"{SCRIPTS_DIR}/yocto-search {term}")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_get_recipe(self):
        """Get (install) a recipe."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            print("\n  Tip: You can search for recipes first with 'Search Recipe'")
            name = input("Enter recipe name to fetch (e.g. nginx): ").strip()
            if name:
                 self._run_command_impl(f"{SCRIPTS_DIR}/yocto-get {name}")
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_new_project(self):
        """Create a new project interactively."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            print("\n  --- New Project Wizard ---\n")
            name = input("  Project Name (e.g. my-app): ").strip()
            if not name:
                print("Cancelled.")
                return

            print("\n  Project Templates:")
            print("  1. cmake   (C++ Application with CMake)")
            print("  2. python  (Python Application)")
            print("  3. script  (Shell Script)")
            print("  4. module  (Kernel Module)")
            
            type_map = {'1': 'cmake', '2': 'python', '3': 'script', '4': 'module'}
            t_choice = input("\n  Select Template [1-4] or Enter for 'cmake': ").strip()
            p_type = type_map.get(t_choice, 'cmake')
            
            # Layer selection could be improved with list, but plain input is okay for now
            # Actually we can use cached layer
            default_layer = yocto_utils.get_cached_layer(self.workspace_root) or "meta-workspace"
            layer = input(f"  Target Layer [default: {default_layer}]: ").strip()
            if not layer:
                layer = default_layer
                
            cmd = f"python3 {SCRIPTS_DIR}/new_project.py {name} --type {p_type} --layer {layer}"
            self._run_command_impl(cmd)
            
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_add_project(self):
        """Add existing project interactively."""
        curses.def_prog_mode()
        curses.endwin()
        try:
            print("\n  --- Add Existing Project ---\n")
            name = input("  Project Name: ").strip()
            if not name:
                return
                
            url = input("  Source URL (git repo or local path): ").strip()
            if not url:
                return

            # Ask for type
            print("\n  Project Type:")
            print("  1. cmake")
            print("  2. python")
            print("  3. makefile")
            print("  4. module")
            print("  5. autotools")
            
            t_choice = input("\n  Select Type [1-5]: ").strip()
            type_map = {'1': 'cmake', '2': 'python', '3': 'makefile', '4': 'module', '5': 'autotools'}
            p_type = type_map.get(t_choice)
            
            type_arg = f"--type {p_type}" if p_type else ""
            
            default_layer = yocto_utils.get_cached_layer(self.workspace_root) or "meta-workspace"
            layer = input(f"  Target Layer [default: {default_layer}]: ").strip()
            if not layer:
                layer = default_layer
                
            cmd = f"python3 {SCRIPTS_DIR}/add_package.py {name} --url {url} --layer {layer} {type_arg}"
            self._run_command_impl(cmd)
        finally:
            curses.reset_prog_mode()
            self.stdscr.refresh()

    def action_live_edit(self):
        """Live edit a recipe."""
        curses.def_prog_mode()
        curses.endwin()
        try:
             # Scan for available recipes to edit? Or just ask name
             # Listing all recipes is slow.
             print("\n  --- Live Edit Recipe (devtool modify) ---\n")
             name = input("  Enter recipe name to edit: ").strip()
             if name:
                 self._run_command_impl(f"python3 {SCRIPTS_DIR}/live_edit.py {name}")
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
