"""
Bookmaker Configuration Loader
Handles loading and accessing bookmaker configuration data.
"""

import json
from pathlib import Path
from typing import Optional, List, Tuple


class BookmakerLoader:
    """
    Loads and provides access to bookmaker configuration data.

    Attributes:
        config_path: Path to bookmaker_config.json
        data: Loaded configuration data
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the loader with config file path.

        Args:
            config_path: Path to bookmaker_config.json. If None, uses default path.
        """
        if config_path is None:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / "data" / "json" / "bookmaker_config.json"

        self.config_path = Path(config_path)
        self.data = self._load_config()

    def _load_config(self) -> dict:
        """Load the JSON configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_bet_limit(self, bookmaker_name: str) -> int:
        """
        Get bet limit for a bookmaker in RSD.

        Args:
            bookmaker_name: Name of the bookmaker (e.g., "Mozzart", "Admiral")

        Returns:
            Bet limit as integer in RSD

        Raises:
            KeyError: If bookmaker not found

        Example:
            >>> loader = BookmakerLoader()
            >>> loader.get_bet_limit("Mozzart")
            100000
        """
        if bookmaker_name not in self.data["bet_limits"]:
            available = list(self.data["bet_limits"].keys())
            raise KeyError(
                f"Bookmaker '{bookmaker_name}' not found. Available: {available}"
            )

        return self.data["bet_limits"][bookmaker_name]["limit_rsd"]

    def are_same_server(self, bookmaker1: str, bookmaker2: str) -> bool:
        """
        Check if two bookmakers share the same Aviator game server.

        Important: Bookmakers on the same server should NOT be tracked simultaneously
        as they produce identical game data.

        Args:
            bookmaker1: First bookmaker name
            bookmaker2: Second bookmaker name

        Returns:
            True if they share the same server, False otherwise

        Example:
            >>> loader = BookmakerLoader()
            >>> loader.are_same_server("Mozzart", "MaxBet")
            True
            >>> loader.are_same_server("Mozzart", "Admiral")
            False
        """
        group1 = self._find_server_group(bookmaker1)
        group2 = self._find_server_group(bookmaker2)

        if group1 is None or group2 is None:
            return False

        return group1["group_id"] == group2["group_id"]

    def _find_server_group(self, bookmaker_name: str) -> Optional[dict]:
        """Find which server group a bookmaker belongs to."""
        for group in self.data["server_groups"]:
            if bookmaker_name in group["bookmakers"]:
                return group
        return None

    def get_server_group_members(self, bookmaker_name: str) -> List[str]:
        """
        Get all bookmakers that share the same server with the given bookmaker.

        Args:
            bookmaker_name: Name of the bookmaker

        Returns:
            List of bookmaker names in the same server group (including the input)

        Example:
            >>> loader = BookmakerLoader()
            >>> loader.get_server_group_members("Mozzart")
            ['Mozzart', 'MaxBet', 'Merkur', 'BetOle']
        """
        group = self._find_server_group(bookmaker_name)
        if group is None:
            return [bookmaker_name]  # Return as single-member group
        return group["bookmakers"]

    def get_stylus_css(self, bookmaker_name: str, formatted: bool = True) -> str:
        """
        Get Stylus CSS configuration for a bookmaker.

        Args:
            bookmaker_name: Name of the bookmaker
            formatted: If True, returns nicely formatted CSS ready for copy-paste.
                      If False, returns raw CSS string.

        Returns:
            CSS configuration string

        Raises:
            KeyError: If bookmaker CSS configuration not found

        Example:
            >>> loader = BookmakerLoader()
            >>> css = loader.get_stylus_css("Mozzart")
            >>> print(css)
            /* Mozzart - https://www.mozzartbet.com/* */

            .navigatio-wrapper {
                display: none;
            }
            ...
        """
        if bookmaker_name not in self.data["stylus_configurations"]:
            available = list(self.data["stylus_configurations"].keys())
            raise KeyError(
                f"Stylus CSS for '{bookmaker_name}' not found. Available: {available}"
            )

        config = self.data["stylus_configurations"][bookmaker_name]
        raw_css = config["css"]

        if not formatted:
            return raw_css

        # Format CSS for better readability
        return self._format_css(bookmaker_name, config["url_pattern"], raw_css)

    def _format_css(self, bookmaker_name: str, url_pattern: str, raw_css: str) -> str:
        """Format CSS into readable, copy-paste ready format."""
        lines = []

        # Header comment
        lines.append(f"/* {bookmaker_name} - {url_pattern} */")
        lines.append("")

        # Parse and format CSS rules
        rules = raw_css.split("\n")
        current_rule = []

        for rule in rules:
            rule = rule.strip()
            if not rule:
                continue

            # Check if it's a selector (doesn't contain ':' or starts with certain patterns)
            if "{" in rule and "}" in rule:
                # Single-line rule: .class {property: value}
                selector, properties = rule.split("{", 1)
                properties = properties.rstrip("}").strip()

                lines.append(f"{selector.strip()} {{")

                # Split multiple properties
                for prop in properties.split(";"):
                    prop = prop.strip()
                    if prop:
                        lines.append(f"    {prop};")

                lines.append("}")
                lines.append("")

            elif "{" in rule:
                # Start of multi-line rule
                current_rule = [rule.rstrip("{").strip() + " {"]

            elif "}" in rule:
                # End of multi-line rule
                current_rule.append("}")
                lines.extend(current_rule)
                lines.append("")
                current_rule = []

            elif current_rule:
                # Inside multi-line rule
                # Format property with proper indentation
                prop = rule.strip()
                if prop and not prop.endswith(";"):
                    prop += ";"
                if prop:
                    current_rule.append(f"    {prop}")

        return "\n".join(lines)

    def validate_betting_setup(
        self, selected_bookmakers: List[str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate betting setup to ensure no bookmakers from the same server are selected.

        Args:
            selected_bookmakers: List of bookmaker names to validate

        Returns:
            Tuple of (is_valid, warning_messages)

        Example:
            >>> loader = BookmakerLoader()
            >>> valid, warnings = loader.validate_betting_setup(["Mozzart", "MaxBet", "Admiral"])
            >>> if not valid:
            ...     for warning in warnings:
            ...         print(warning)
            WARNING: Mozzart and MaxBet share the same server!
        """
        warnings = []
        is_valid = True

        checked_pairs = set()

        for i, bm1 in enumerate(selected_bookmakers):
            for bm2 in selected_bookmakers[i + 1 :]:
                pair = tuple(sorted([bm1, bm2]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                if self.are_same_server(bm1, bm2):
                    is_valid = False
                    group_members = self.get_server_group_members(bm1)
                    warnings.append(
                        f"⚠️  WARNING: '{bm1}' and '{bm2}' share the same server! "
                        f"This will create duplicate data. Server group: {group_members}"
                    )

        return is_valid, warnings

    def get_all_bookmakers(self) -> List[str]:
        """Get list of all available bookmakers."""
        return list(self.data["bet_limits"].keys())

    def get_betting_tier(self, bookmaker_name: str) -> str:
        """
        Get betting tier for a bookmaker.

        Args:
            bookmaker_name: Name of the bookmaker

        Returns:
            Tier: 'premium', 'medium', 'standard', or 'low'
        """
        if bookmaker_name not in self.data["bet_limits"]:
            raise KeyError(f"Bookmaker '{bookmaker_name}' not found")

        return self.data["bet_limits"][bookmaker_name]["tier"]


# Example usage and testing
if __name__ == "__main__":
    # Initialize loader
    loader = BookmakerLoader()

    print("=" * 60)
    print("BOOKMAKER LOADER - DEMO")
    print("=" * 60)

    # Test 1: Get bet limits
    print("\n1. BET LIMITS:")
    print("-" * 60)
    for bm in ["Mozzart", "Admiral", "BalkanBet", "VolcanoBet"]:
        limit = loader.get_bet_limit(bm)
        tier = loader.get_betting_tier(bm)
        print(f"  {bm:15} - {limit:>7,} RSD ({tier})")

    # Test 2: Check same server
    print("\n2. SERVER CHECKING:")
    print("-" * 60)
    test_pairs = [
        ("Mozzart", "MaxBet"),
        ("Mozzart", "Admiral"),
        ("Admiral", "Meridian"),
        ("BalkanBet", "King"),
    ]
    for bm1, bm2 in test_pairs:
        same = loader.are_same_server(bm1, bm2)
        result = "✓ SAME SERVER" if same else "✗ Different servers"
        print(f"  {bm1} vs {bm2:12} - {result}")

    # Test 3: Server group members
    print("\n3. SERVER GROUP MEMBERS:")
    print("-" * 60)
    for bm in ["Mozzart", "Admiral", "BalkanBet"]:
        members = loader.get_server_group_members(bm)
        print(f"  {bm:15} - {', '.join(members)}")

    # Test 4: Validate betting setup
    print("\n4. BETTING SETUP VALIDATION:")
    print("-" * 60)
    test_setups = [
        ["Mozzart", "Admiral", "BalkanBet"],  # Valid
        ["Mozzart", "MaxBet", "Admiral"],  # Invalid - Mozzart & MaxBet same server
    ]
    for setup in test_setups:
        valid, warnings = loader.validate_betting_setup(setup)
        print(f"\n  Setup: {setup}")
        print(f"  Valid: {'✓ YES' if valid else '✗ NO'}")
        if warnings:
            for warning in warnings:
                print(f"    {warning}")

    # Test 5: Stylus CSS (just show one example)
    print("\n5. STYLUS CSS EXAMPLE (Mozzart):")
    print("-" * 60)
    css = loader.get_stylus_css("Mozzart")
    print(css[:300] + "...")  # Show first 300 chars

    print("\n" + "=" * 60)
