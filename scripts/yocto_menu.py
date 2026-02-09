#!/usr/bin/env python3
"""
Yocto Menu - A TUI for managing the Yocto workspace.
"""
import curses
import os
import subprocess
import sys
import time
import contextlib
from pathlib import Path
from typing import List, Tuple, Callable, Optional

# Add scripts dir to path to import yocto_utils
SCRIPTS_DIR = Path(__file__).parent.resolve()
sys.path.append(str(SCRIPTS_DIR))

try:
    import yocto_utils
    import config_manager
    import update_image
    from yocto_layer_index import LayerIndex, DEFAULT_BRANCH
    from yocto_utils import get_yocto_branch
except ImportError:
    # Fallback if running standalone without yocto_utils nearby
    yocto_utils = None
    config_manager = None
    update_image = None
    LayerIndex = None
    DEFAULT_BRANCH = "master"
    get_yocto_branch = lambda x: DEFAULT_BRANCH

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

class MarkdownViewer:
    """Simple Curses-based Markdown Viewer."""
    def __init__(self, title: str, content: str):
        self.title = title
        self.content = content
        self.lines = self._parse_content(content)
        self.scroll_y = 0
        self.running = True
        self.stdscr = None
        
    def _parse_content(self, content: str) -> List[Tuple[str, int]]:
        """Parse markdown into lines with color attributes."""
        parsed = []
        in_code_block = False
        
        for line in content.splitlines():
            # Code Blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                parsed.append((line, curses.color_pair(3) | curses.A_DIM)) # Cyan-ish
                continue
            
            if in_code_block:
                parsed.append((line, curses.color_pair(3)))
                continue

            # Headers
            if line.strip().startswith("#"):
                level = len(line.split(' ')[0])
                # Clean header
                clean_line = line.strip().lstrip('#').strip()
                # Center main title, left align others
                if level == 1:
                    parsed.append(("", 0)) # Spacing
                    parsed.append((clean_line.upper(), curses.color_pair(2) | curses.A_BOLD))
                    parsed.append(("", 0))
                else:
                    parsed.append((clean_line, curses.color_pair(2) | curses.A_BOLD))
                continue
            
            # Lists
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                parsed.append((line, 0))
                continue
            
            # Quotes
            if line.strip().startswith(">"):
                parsed.append((line, curses.color_pair(4) | curses.A_ITALIC))
                continue

            # Default
            parsed.append((line, 0))
            
        return parsed

    def start(self):
        curses.wrapper(self._main_loop)

    def _main_loop(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        
        # Ensure colors are init (if running standalone)
        # But we actully call this from main app which inits colors.
        # Re-init just in case doesn't hurt or just relly on existing
        
        while self.running:
            self._draw()
            key = self.stdscr.getch()
            self._handle_input(key)

    def _draw(self):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Use safe width (width - 1) to avoid writing to the last column
        # which can cause issues in some terminals or bottom-right corner
        safe_width = width - 1
        
        # Header
        self.stdscr.attron(curses.color_pair(3) | curses.A_REVERSE)
        header = f" {self.title} "
        try:
            self.stdscr.addstr(0, 0, f"{header:<{safe_width}}")
        except curses.error:
            pass
        self.stdscr.attroff(curses.color_pair(3) | curses.A_REVERSE)
        
        # Content Area
        max_lines = height - 2 # Header + Footer
        
        for i in range(max_lines):
            line_idx = self.scroll_y + i
            if line_idx >= len(self.lines):
                break
                
            text, attr = self.lines[line_idx]
            # Truncate to width-2 (start at x=1, leave 1 space at right)
            content_width = max(1, width - 2)
            text = text[:content_width]
            
            if attr:
                self.stdscr.attron(attr)
            
            try:
                self.stdscr.addstr(i + 1, 1, text)
            except curses.error:
                pass # Ignore edge case errors
                
            if attr:
                self.stdscr.attroff(attr)

        # Footer
        footer = " Scroll: \u2191\u2193/PgUp/PgDn | Exit: q "
        # Ensure footer fits
        footer = f"{footer:<{safe_width}}"[:safe_width]
        try:
            self.stdscr.addstr(height - 1, 0, footer, curses.color_pair(1) | curses.A_DIM)
        except curses.error:
            pass # Writing to bottom-right corner often returns ERR but succeeds
        
        self.stdscr.refresh()

    def _handle_input(self, key):
        height, _ = self.stdscr.getmaxyx()
        page_size = height - 2
        
        if key == ord('q') or key == 27:
            self.running = False
        elif key == curses.KEY_UP:
            self.scroll_y = max(0, self.scroll_y - 1)
        elif key == curses.KEY_DOWN:
            self.scroll_y = min(max(0, len(self.lines) - page_size), self.scroll_y + 1)
        elif key == curses.KEY_NPAGE: # Page Down
            self.scroll_y = min(max(0, len(self.lines) - page_size), self.scroll_y + page_size)
        elif key == curses.KEY_PPAGE: # Page Up
            self.scroll_y = max(0, self.scroll_y - page_size)
        elif key == curses.KEY_HOME:
            self.scroll_y = 0
        elif key == curses.KEY_END:
            self.scroll_y = max(0, len(self.lines) - page_size)

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
        
        # State
        self.current_branch = None
        if yocto_utils:
            self.current_branch = yocto_utils.get_yocto_branch(self.workspace_root)
        if not self.current_branch:
             self.current_branch = "master"

    @contextlib.contextmanager
    def _suppress_output(self):
        """Context manager to suppress stdout/stderr."""
        if self.stdscr: # Only if in curses mode
            with open(os.devnull, 'w') as devnull:
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = devnull
                sys.stderr = devnull
                try:
                    yield
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
        else:
            yield

    def _find_workspace_root(self) -> Path:
        """Find the workspace root (parent of scripts dir)."""
        return SCRIPTS_DIR.parent

    def _build_menus(self) -> Menu:
        """Define the menu structure."""
        
        # Build & Run Submenu
        build_menu = Menu("Build & Run", [
            MenuItem("Select Default Image", self.action_select_image, "Select the default image for build/run"),
            MenuItem("Build Image", self.action_build_image, "Build an image recipe"),
            MenuItem("Run in QEMU", self.action_run_qemu, "Run a built image in QEMU"),
            MenuItem("Flash to SD Card", f"python3 {SCRIPTS_DIR}/yocto_flash.py", "Safely write image to SD card/USB"),
            MenuItem("Build SDK", self.action_build_sdk, "Build the SDK for cross-development"),
            MenuItem("Deploy Recipe", self.action_deploy_recipe, "Deploy build artifacts to target"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Projects Submenu
        project_menu = Menu("Project Management", [
            MenuItem("New Project", self.action_new_project, "Create a new project"),
            MenuItem("Add Existing Project", self.action_add_project, "Add an existing project to the workspace"),
            MenuItem("Sync Project Deps", f"python3 {SCRIPTS_DIR}/sync_deps.py", "Sync CMake dependencies with Yocto recipes"),
            MenuItem("Live Edit Recipe", self.action_live_edit, "Edit a recipe in the workspace"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])
        
        # Layers Submenu
        layer_menu = Menu("Layer Management", [
            MenuItem("New Layer", self.action_add_layer, "Create a new Yocto layer"),
            MenuItem("Sync Layers", f"python3 {SCRIPTS_DIR}/layer_manager.py", "Synchronize layer configurations"),
            MenuItem("Layer Info", f"python3 {SCRIPTS_DIR}/layer_manager.py --info --interactive", "View layer details and recipes"),
            MenuItem("Back", self.go_back, "Return to main menu")
        ])

        # Configuration Submenu
        config_menu = Menu("Configuration", [
            MenuItem("List Machines", self.action_list_machines, "List and switch target machines"),
            MenuItem("Select Search Branch", self.action_select_branch, "Set Yocto release branch for searches"),
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
            MenuItem("Show Last Error", f"python3 {SCRIPTS_DIR}/last_error.py", "Show log of last failed build task"),
            MenuItem("Check Layers", f"python3 {SCRIPTS_DIR}/check_layer.py", "Sanity check local layers"),
            MenuItem("Search Recipe", self.action_search_recipe, "Search for recipes in Layer Index"),
            MenuItem("Get Recipe", self.action_get_recipe, "Fetch and install a recipe"),
            MenuItem("Visualize Dependencies", self.prompt_dependency_viz, "Visualize project dependencies"),
            MenuItem("Inspect Variable", self.action_query_variable, "Query BitBake variable value"),
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
            MenuItem("Documentation", self.action_view_docs, "View tooling guide"),
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
                branch = self.current_branch or "master"
                status_text = f"Machine: {machine} | Branch: {branch} | Image: {image}"
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
            self.stdscr.hline(height - 4, 2, curses.ACS_HLINE, width - 4)
            self.stdscr.addstr(height - 3, 4, description, curses.color_pair(4))

        # Keybinding Help
        help_text = "Navigate: ↑↓ | Select: Enter | Back: q"
        self.stdscr.addstr(height - 1, 2, help_text, curses.color_pair(1) | curses.A_DIM)
        
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

    def action_list_machines(self):
        """Native menu to list and switch machines."""
        if not yocto_utils:
            return
            
        machines_dict = yocto_utils.get_available_machines(self.workspace_root)
        current = yocto_utils.get_machine_from_config(self.workspace_root)
        
        items = []
        
        # Helper to add items
        def add_machine_item(name, category):
            label = name
            desc = f"Switch to {name} ({category})"
            if name == current:
                label = f"{name} *"
                desc = f"Current machine ({category})"
            
            items.append(MenuItem(label, lambda m=name: self._confirm_switch_machine(m), desc))

        # Custom Machines
        for m in machines_dict.get('custom', []):
            add_machine_item(m, "Custom Layer")
            
        # Poky Machines
        for m in machines_dict.get('poky', []):
            add_machine_item(m, "Poky Standard")
            
        menu = Menu("Available Machines", items)
        self.enter_menu(menu)

    def _confirm_switch_machine(self, machine):
        # We can switch immediately
        # Using machine_manager to do the switch
        cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py switch {machine}"
        self.run_shell_command(cmd)
        # We might want to refresh the menu or header?
        # Header refreshes automatically in draw_screen
        self.go_back()


    def action_select_branch(self):
        """Select the active Yocto branch for searches."""
        current = self.current_branch or "master"
        new_branch = self.get_input(f"Enter Release Branch [current: {current}]:")
        
        if new_branch:
             self.current_branch = new_branch
             self.show_message(f"Search branch set to: {self.current_branch}")


    def action_run_qemu(self):
        """Run an image in QEMU."""
        # Finds built images
        images_list = yocto_utils.find_built_images(self.workspace_root)
        if not images_list:
             self.show_message("No built images found to run.")
             return

        # Explicitly deduplicate by name
        seen = set()
        unique_images = []
        for img in images_list:
            if img['name'] not in seen:
                 seen.add(img['name'])
                 unique_images.append(img)
        
        items = []
        for img in unique_images:
             # run_qemu.py takes image name
             items.append(MenuItem(img['name'], lambda i=img['name']: self._perform_run_qemu(i), f"Run {i}"))
             
        menu = Menu("Select Image to Run", items)
        self.enter_menu(menu)
        
    def _perform_run_qemu(self, image):
        # We need to run this and NOT capture output (let it take over terminal completely)
        # run_qemu.py is interactive typically
        cmd = f"python3 {SCRIPTS_DIR}/run_qemu.py {image}"
        self.run_shell_command(cmd)


    def action_build_image(self):
        """Build an image recipe."""
        # 1. Try to find image recipes in custom layers
        recipes = []
        try:
             # Scan all custom layers for image recipes
             layers = yocto_utils.get_all_custom_layers(self.workspace_root)
             for layer in layers:
                  layer_recipes = yocto_utils.find_image_recipes(layer)
                  recipes.extend(layer_recipes)
        except Exception:
             pass
             
        # Add basic images if list is empty or just as option?
        # Let's add standard ones if we can't find any, or always?
        # Keeping it simple: Custom images first.
        
        # Also allow building "current" image if set
        cached = yocto_utils.get_cached_image(self.workspace_root)
        
        items = []
        if cached:
             items.append(MenuItem(f"Build '{cached}' (Last Used)", lambda: self._perform_build(cached), "Build the last used image"))
             
        seen = set()
        if cached: seen.add(cached)
        
        for r in sorted(recipes):
             if r not in seen:
                 items.append(MenuItem(r, lambda x=r: self._perform_build(x), f"Build {r}"))
                 seen.add(r)
        
        # Manual entry option
        items.append(MenuItem("Enter manually...", self._build_manual, "Type recipe name"))
        
        menu = Menu("Select Image to Build", items)
        self.enter_menu(menu)
        
    def _perform_build(self, image):
        cmd = f"python3 {SCRIPTS_DIR}/build_recipe.py {image}"
        self.run_shell_command(cmd)
        
    def _build_manual(self):
        name = self.get_input("Image Recipe Name:")
        if name:
             self._perform_build(name)


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
        term = self.get_input("Enter machine name to search:")
        
        if not term:
            return

        self.show_message(f"Searching for '{term}'...", wait=False)
        curses.doupdate()
        
        try:
            branch = self.current_branch
            index = LayerIndex(branch=branch)
            # This might take a second, message above helps
            with self._suppress_output():
                machines = index.search_machines(term)
        except Exception as e:
            self.show_message(f"Search failed: {e}")
            return

        if not machines:
            self.show_message(f"No machines found for '{term}' in branch '{branch}'.")
            return

        items = []
        for m in machines:
             # We need layer info for context
             info = index.get_machine_layer_info(m)
             if info:
                 label = f"{info['machine_name']} ({info['layer_name']})"
                 desc = info.get('description', '')[:60]
                 # Action: Fetch
                 items.append(MenuItem(label, lambda m=m['name']: self._perform_get_machine(m), desc))

        if not items:
            self.show_message("Found matches but failed to resolve layer info.")
            return

        menu = Menu(f"Search Results: '{term}'", items)
        self.enter_menu(menu)
    
    def _perform_get_machine(self, machine_name):
        cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py get {machine_name}"
        self.run_shell_command(cmd)
        self.go_back()

    def action_get_machine(self):
        """Get (install) a machine."""
        name = self.get_input("Enter machine name to install:")
        if name:
            cmd = f"python3 {SCRIPTS_DIR}/machine_manager.py get {name}"
            self.run_shell_command(cmd)

    def action_get_recipe(self):
        """Get (install) a recipe."""
        self.show_message("Tip: You can search for recipes first with 'Search Recipe'", wait=False)
        curses.doupdate()
        time.sleep(1.5) # Short pause so they see the tip
        
        name = self.get_input("Enter recipe name to fetch (e.g. nginx):")
        if name:
             self.run_shell_command(f"{SCRIPTS_DIR}/yocto-get {name}")

    def action_live_edit(self):
        """Edit a workspace recipe."""
        # Find recipes in workspace (meta-workspace/recipes-*)
        try:
             # Borrow logic? Or use yocto_utils?
             # yocto_utils.find_image_recipes gets images.
             # We want all recipes in workspace layer.
             layer = yocto_utils.get_cached_layer(self.workspace_root) or "meta-workspace"
             # We need to find the path
             layer_path = yocto_utils.find_layer_path(self.workspace_root, layer)
             if not layer_path:
                  self.show_message(f"Could not find layer {layer}")
                  return
                  
             # Simple glob for .bb files
             import glob
             recipes = []
             for f in glob.glob(f"{layer_path}/recipes-*/*/*.bb"):
                  recipes.append(os.path.basename(f))
             
             if not recipes:
                  self.show_message("No recipes found in workspace.")
                  return
                  
             items = []
             for r in sorted(recipes):
                  items.append(MenuItem(r, lambda x=r: self._perform_edit(layer_path, x), "Edit this recipe"))
                  
             menu = Menu("Select Recipe to Edit", items)
             self.enter_menu(menu)
        except Exception as e:
             self.show_message(f"Error listing recipes: {e}")

    def _perform_edit(self, layer_path, recipe_file):
        # Find full path again
        import glob
        files = glob.glob(f"{layer_path}/recipes-*/*/{recipe_file}")
        if files:
             path = files[0]
             editor = os.environ.get("EDITOR", "vim")
             self.run_shell_command(f"{editor} {path}")


    def action_deploy_recipe(self):
        """Deploy a recipe to a target."""
        # TODO: Auto-detect built recipes to offer a list?
        # For now, just ask for recipe name.
        name = self.get_input("Enter recipe name to deploy:")
        if name:
            # Check if we have remote target set?
            # deploy_recipe.py handles args. 
            # We can prompt for remote target IP optionally?
            remote = self.get_input("Remote target (user@IP) [optional]:")
            
            cmd = f"python3 {SCRIPTS_DIR}/deploy_recipe.py {name}"
            if remote:
                cmd += f" --remote {remote}"
                
            self.run_shell_command(cmd)

    def action_query_variable(self):
        """Query a Yocto variable."""
        var = self.get_input("Variable Name (e.g. WORKDIR):")
        if var:
            # Optional recipe context
            recipe = self.get_input("Recipe Context [optional]:")
            cmd = f"python3 {SCRIPTS_DIR}/yocto_query.py {var}"
            if recipe:
                cmd += f" {recipe}"
            self.run_shell_command(cmd)

    def action_view_docs(self):
        """View the documentation."""
        doc_path = self.workspace_root / "docs" / "tooling-guide.md"
        if not doc_path.exists():
            self.show_message("Documentation not found.")
            return

        try:
            content = doc_path.read_text()
            
            # Temporarily suspend main menu loop
            # But wait, MarkdownViewer uses curses.wrapper which might re-init curses.
            # We are ALREADY in a curses wrapper from YoctoMenuApp.
            # So we should call viewer._main_loop(self.stdscr) directly?
            # Or better, just make MarkdownViewer take the window and run its own loop
            # without wrapper.
            
            # Let's adjust MarkdownViewer usage here to be safe within existing loop
            viewer = MarkdownViewer("Tooling Guide", content)
            
            # We need to save current screen state?
            # Actually, just running viewer's loop on the same stdscr is fine.
            # It handles its own drawing.
            # When it returns, we just redraw our own screen.
            viewer._main_loop(self.stdscr)
            
            # Restore our screen
            self.draw_screen()
            
        except Exception as e:
            self.show_message(f"Error viewing docs: {e}")


    def action_build_sdk(self):
        """Build SDK for an image."""
        # Reuse logic from build_image but different callback
        recipes = []
        try:
             layers = yocto_utils.get_all_custom_layers(self.workspace_root)
             for layer in layers:
                  recipes.extend(yocto_utils.find_image_recipes(layer))
        except: pass
        
        cached = yocto_utils.get_cached_image(self.workspace_root)
        
        items = []
        if cached:
             items.append(MenuItem(f"Build SDK for '{cached}'", lambda: self._perform_build_sdk(cached), "Build SDK for last used image"))
             
        seen = set()
        if cached: seen.add(cached)
        
        for r in sorted(recipes):
             if r not in seen:
                 items.append(MenuItem(r, lambda x=r: self._perform_build_sdk(x), f"Build SDK for {r}"))
                 seen.add(r)
        
        items.append(MenuItem("Enter manually...", self._build_sdk_manual, "Type image name"))
        
        menu = Menu("Select Image for SDK", items)
        self.enter_menu(menu)
        
    def _perform_build_sdk(self, image):
        # manage_sdk.py uses positional arg for image
        cmd = f"python3 {SCRIPTS_DIR}/manage_sdk.py --build {image}"
        self.run_shell_command(cmd)

    def _build_sdk_manual(self):
        name = self.get_input("Image Recipe Name:")
        if name:
             self._perform_build_sdk(name)


    def action_manage_fragments(self):
        """Submenu for fragment management."""
        options = [
            ("List Active Fragments", self.action_list_fragments),
            ("List Available Fragments", self.action_list_available_fragments),
            ("Back", self.go_back)
        ]
        
        items = [MenuItem(label, action) for label, action in options]
        menu = Menu("Fragment Management", items)
        self.enter_menu(menu)



    def action_list_fragments(self):
        """Show active fragments in a submenu."""
        fragments = config_manager.get_fragments()
        if not fragments:
            self.show_message("No active fragments.")
            return

        items = []
        for f in fragments:
            # Clicking an active fragment offers to disable it
            items.append(MenuItem(f, lambda f=f: self._confirm_disable_fragment(f), "Select to disable"))
        
        menu = Menu("Active Fragments", items)
        self.enter_menu(menu)
    
    def _confirm_disable_fragment(self, fragment):
        # We can just disable it and refresh the menu, or ask confirmation.
        # For speed, let's just disable and show message.
        config_manager.disable_fragment(fragment)
        self.show_message(f"Disabled {fragment}")
        self.go_back() # Go back to manage fragments or refresh current? 
        # Ideally we refresh. But our simple menu system doesn't auto-refresh.
        # So going back to parenting menu is safest.

    def action_list_available_fragments(self):
        """Show available fragments in a submenu."""
        available = config_manager.get_available_fragments()
        active = config_manager.get_fragments()
        
        if not available:
            self.show_message("No fragments found in layers (conf/fragments/*.conf).")
            return

        items = []
        for name in sorted(available.keys()):
            if name not in active:
                items.append(MenuItem(name, lambda f=name: self._confirm_enable_fragment(f), "Select to Enable"))

        menu = Menu("Available Fragments", items)
        self.enter_menu(menu)

    def _confirm_enable_fragment(self, fragment):
        config_manager.enable_fragment(fragment)
        self.show_message(f"Enabled {fragment}")
        self.go_back()

    def get_input(self, prompt: str) -> str:
        """Get text input from the user via curses."""
        h, w = self.stdscr.getmaxyx()
        # Create a centered window
        win_h, win_w = 4, min(60, w - 4)
        win_y, win_x = (h - win_h) // 2, (w - win_w) // 2
        
        win = curses.newwin(win_h, win_w, win_y, win_x)
        win.box()
        win.addstr(1, 2, prompt[:win_w-4])
        win.refresh()
        
        curses.echo()
        curses.curs_set(1)
        
        input_str = ""
        try:
            # simple getstr
            # enable echo for visibility
            input_bytes = win.getstr(2, 2, win_w - 4)
            input_str = input_bytes.decode('utf-8').strip()
        except:
             pass
        finally:
            curses.noecho()
            curses.curs_set(0)
            
        return input_str

    def show_message(self, msg, wait=True):
        """Helper to show a message in curses without leaving."""
        h, w = self.stdscr.getmaxyx()
        
        # Calculate width based on message, max 80% screen, min 40 chars
        win_w = max(40, min(w - 4, len(msg) + 6))
        win_h = 5
        
        # Center the window
        win_y = (h - win_h) // 2
        win_x = (w - win_w) // 2
        
        msg_win = curses.newwin(win_h, win_w, win_y, win_x)
        msg_win.box()
        
        # Center the text
        text_x = max(1, (win_w - len(msg)) // 2)
        msg_win.addstr(2, text_x, msg[:win_w-2])
        
        if wait:
            prompt = "Press any key..."
            prompt_x = max(1, (win_w - len(prompt)) // 2)
            msg_win.addstr(3, prompt_x, prompt)
        
        msg_win.refresh()
        
        if wait:
            msg_win.getch()

    # Image Package Management Actions
    def action_manage_packages(self):
        """Submenu for image package management."""
        options = [
            ("List Installed Packages", self.action_list_packages),
            ("Add Package", self.action_add_package),
            ("Remove Package", self.action_remove_package),
            ("Refresh Workspace", self.refresh_image_wrapper),
            ("Back", self.go_back)
        ]
        items = [MenuItem(label, action) for label, action in options]
        menu = Menu("Manage Image Packages", items)
        self.enter_menu(menu)


    def refresh_image_wrapper(self):
         self.run_shell_command(f"python3 {SCRIPTS_DIR}/update_image.py refresh")

    def action_list_packages(self):
        """Native menu for listing packages."""
        try:
            _, image_name, packages = update_image.get_current_image_info(self.workspace_root)
        except Exception as e:
            self.show_message(f"Error getting image info: {e}")
            return

        items = []
        for pkg in packages:
             items.append(MenuItem(pkg, lambda p=pkg: self._confirm_remove_package(p), "Select to Remove"))
        
        menu = Menu(f"Packages in {image_name}", items)
        self.enter_menu(menu)
    
    def _confirm_remove_package(self, pkg):
        # We'll use the proper remove command but implementing via shell wrapper for now 
        # or we could call update_image directly?
        # Direct call would be better but we need to pass args object.
        # Let's keep using _run_command_impl for the actual modification to ensure user sees output
        # But wait, avoiding shell is the goal? 
        # Actually user wants "IN the menus". Output of the command is fine, but the *LIST* should be menu.
        # Let's execute removal then showing message.
        
        # We need to call update_image logic.
        # It's safer to use CLI wrapper for the ACTION phase to show potential errors/logs, 
        # then return to menu (which refreshes).
        
        self.run_shell_command(f"python3 {SCRIPTS_DIR}/update_image.py remove {pkg}")
        # After return, we are back in the list menu? No, run_shell_command refreshes screen but
        # our Menu object might need reloading? 
        # The Menu object's items are static. We need to refresh the list.
        # So we should go back, then re-enter?
        self.go_back()
        self.action_list_packages() # Re-open updated list

    def action_add_package(self):
        """Search and add package."""
        term = self.get_input("Enter package name to search:")
        
        if not term:
            return
            
        # Use search to find candidates
        try:
            candidates = update_image.scan_all_recipes(self.workspace_root)
            matches = [c for c in candidates if term in c]
            
            if not matches:
                 self.show_message(f"No matches found for '{term}'")
                 # Check if they want to force add? 
                 # For now just return, simpler for native UI
                 return
        except Exception as e:
            self.show_message(f"Error scanning packages: {e}")
            return
            
        # Now show matches in a menu
        if matches:
            items = []
            for m in matches:
                items.append(MenuItem(m, lambda p=m: self._perform_add(p), "Select to Add"))
            
            menu = Menu(f"Add Package: '{term}'", items)
            self.enter_menu(menu)
            
    def _perform_add(self, pkg):
        self.run_shell_command(f"python3 {SCRIPTS_DIR}/update_image.py add {pkg}")
        self.go_back() # Go back to search results? Or root?
        # Go back to management menu
        self.go_back()

    def action_remove_package(self):
        # Alias to list, as listing allows removal
        self.action_list_packages()

    def action_search_recipe(self):
        """Search for a recipe in the Layer Index."""
        term = self.get_input("Enter recipe name to search:")

        if not term:
            return

        self.show_message(f"Searching for '{term}'...", wait=False)
        curses.doupdate()
        
        try:
            branch = self.current_branch
            index = LayerIndex(branch=branch)
            with self._suppress_output():
                recipes = index.search_recipes(term)
            
        except Exception as e:
            self.show_message(f"Search failed: {e}")
            return
            
        if not recipes:
            self.show_message(f"No recipes found for '{term}' in branch '{branch}'.")
            return

        items = []
        # sort by similarity or just alphabetical?
        # Exact match first
        recipes.sort(key=lambda x: (x['pn'] != term, x['pn']))

        for r in recipes[:30]: # Limit results
             info = index.get_recipe_layer_info(r)
             if info:
                 label = f"{info['recipe_name']} ({info['layer_name']})"
                 desc = info.get('summary', '')[:60]
                 items.append(MenuItem(label, lambda r=r['pn']: self._perform_get_recipe(r), desc))

        menu = Menu(f"Search Results: '{term}'", items)
        self.enter_menu(menu)
    
    def _perform_get_recipe(self, recipe_name):
        cmd = f"{SCRIPTS_DIR}/yocto-get {recipe_name}"
        self.run_shell_command(cmd)
        self.go_back()



    def action_new_project(self):
        """Create a new project interactively."""
        name = self.get_input("Project Name (e.g. my-app):")
        if not name:
            return

        # Template Selection matching new_project.py choices
        templates = [
            ("cmake", "C++ Application (CMake)"),
            ("python", "Python Application"),
            ("module", "Kernel Module"),
            ("rust",  "Rust Application"),
            ("go",    "Go Application")
        ]
        
        # We need to capture the name in the closure
        def pick_template(t_id):
            # Default layer
            layer = yocto_utils.get_cached_layer(self.workspace_root) or "meta-workspace"
            
            # Run command
            cmd = f"python3 {SCRIPTS_DIR}/new_project.py {name} --type {t_id} --layer {layer}"
            self.run_shell_command(cmd)
            # Return to previous menu
            self.go_back()

        items = []
        for t_id, t_desc in templates:
            items.append(MenuItem(t_desc, lambda t=t_id: pick_template(t), t_desc))
            
        menu = Menu("Select Project Template", items)
        self.enter_menu(menu)

    def action_add_project(self):
        """Add existing project interactively."""
        name = self.get_input("Project Name:")
        if not name:
            return
            
        url = self.get_input("Source URL (git repo or local path):")
        if not url:
            return

        # Project Type Selection
        types = [
            ("cmake", "CMake Project"),
            ("python", "Python Project"),
            ("makefile", "Makefile Project"),
            ("module", "Kernel Module"),
            ("autotools", "Autotools Project")
        ]
        
        def pick_type(p_type):
            # Default layer
            layer = yocto_utils.get_cached_layer(self.workspace_root) or "meta-workspace"
            
            type_arg = f"--type {p_type}" if p_type else ""
            cmd = f"python3 {SCRIPTS_DIR}/add_package.py {name} --url {url} --layer {layer} {type_arg}"
            
            self.run_shell_command(cmd)
            self.go_back()

        items = []
        for t_id, t_desc in types:
            items.append(MenuItem(t_desc, lambda t=t_id: pick_type(t), t_desc))
            
        menu = Menu("Select Project Type", items)
        self.enter_menu(menu)

    def action_list_layers(self):
        """Native menu to list and manage layers."""
        layers = yocto_utils.get_bblayers(self.workspace_root)
        
        items = []
        for layer in layers:
            # Shorten path for display
            display_name = layer.name
            if str(layer).startswith(str(self.workspace_root)):
                 display_path = str(layer.relative_to(self.workspace_root))
            else:
                 display_path = str(layer)
                 
            # Action: Show details (or remove?)
            # For now, just show details or allowed actions
            items.append(MenuItem(f"{display_name} ({display_path})", lambda l=layer: self._layer_details(l), "View layer details"))
            
        menu = Menu("List Layers", items)
        self.enter_menu(menu)

    def action_add_layer(self):
        """Wizard to add/create a layer."""
        name = self.get_input("Layer Name (e.g. meta-myfeature):")
        if not name: return
        
        # Optional: Priority
        prio = self.get_input("Priority [default: 6]:")
        if not prio: prio = "6"
        
        # We can use yocto-layers script
        # yocto-layers --new creates it
        cmd = f"python3 {SCRIPTS_DIR}/layer_manager.py --new {name} --priority {prio}"
        self.run_shell_command(cmd)
        self.go_back()
        # Refresh parent list
        self.go_back()
        self.action_list_layers()

    def _layer_details(self, layer_path):
        # Submenu for a specific layer
        items = [
            MenuItem("Back", self.go_back, "Return to layer list")
            # We could add "Remove Layer" here if we implement it safely
        ]
        
        # Count recipes?
        recipes = list(layer_path.glob("recipes-*/*/*.bb"))
        
        menu = Menu(f"Layer: {layer_path.name}", items)
        # We can't easily show text in a Menu without items, so maybe just a message for now?
        # Or a "Remove" action if it's a custom layer.
        
        is_custom = "yocto/layers" in str(layer_path)
        if is_custom:
             items.insert(0, MenuItem("Remove Layer", lambda: self.show_message("Removal not yet implemented (use bitbake-layers remove-layer)"), "Remove this layer from bblayers.conf"))
        
        self.show_message(f"Path: {layer_path}\nRecipes: {len(recipes)}")
        # self.enter_menu(menu) # Not really useful yet unless we have actions

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
