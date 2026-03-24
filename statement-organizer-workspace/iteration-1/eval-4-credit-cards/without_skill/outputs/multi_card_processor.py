#!/usr/bin/env python3
"""
Multi-Card Credit Statement Processor
Handles detection and processing of AmEx, Chase, and Visa statements
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class CardType(Enum):
    """Supported credit card types"""
    AMEX = "amex"
    CHASE = "chase"
    VISA = "visa"
    UNKNOWN = "unknown"


@dataclass
class FormatSignature:
    """Signature of a card format for identification"""
    card_type: CardType
    confidence: float
    indicators: List[str]


class CardFormatDetector:
    """Detects credit card statement formats"""

    def __init__(self, mappings_dir: str = "."):
        """Initialize detector with format mappings"""
        self.mappings = self._load_mappings(mappings_dir)
        self.detection_rules = self._build_detection_rules()

    def _load_mappings(self, mappings_dir: str) -> Dict[str, dict]:
        """Load format mappings from JSON files"""
        mappings = {}
        mapping_files = {
            "amex": "amex_format_mapping.json",
            "chase": "chase_format_mapping.json",
            "visa": "visa_format_mapping.json"
        }

        for card_type, filename in mapping_files.items():
            path = os.path.join(mappings_dir, filename)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    mappings[card_type] = json.load(f)
        return mappings

    def _build_detection_rules(self) -> Dict[CardType, dict]:
        """Build detection rules from mappings"""
        rules = {}
        for card_type, mapping in self.mappings.items():
            patterns = mapping.get("identifier_patterns", {})
            rules[card_type] = {
                "headers": patterns.get("statement_header", "").split("|"),
                "card_prefix": patterns.get("card_number_prefix", ""),
                "date_formats": patterns.get("date_format", "").split("|")
            }
        return rules

    def detect_format(self, file_path: str) -> FormatSignature:
        """
        Detect which credit card format a file uses

        Args:
            file_path: Path to statement file

        Returns:
            FormatSignature with detected type and confidence
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return FormatSignature(CardType.UNKNOWN, 0.0, [])

        scores = {}

        # Check for header patterns
        for card_type, patterns in self.rules.items():
            score = 0
            indicators = []

            for header in patterns["headers"]:
                if re.search(header, content, re.IGNORECASE):
                    score += 40
                    indicators.append(f"Found header: {header}")

            # Check for distinctive features
            features = self.mappings[card_type].get("distinctive_features", [])
            for feature in features:
                if feature.lower() in content.lower():
                    score += 10
                    indicators.append(f"Found feature: {feature}")

            scores[card_type] = (score, indicators)

        # Find best match
        if not scores:
            return FormatSignature(CardType.UNKNOWN, 0.0, [])

        best_card_type = max(scores.items(), key=lambda x: x[1][0])
        card_type_str, (score, indicators) = best_card_type

        # Convert string to enum
        try:
            card_type_enum = CardType[card_type_str.upper()]
        except KeyError:
            card_type_enum = CardType.UNKNOWN

        confidence = min(score / 100.0, 1.0)
        return FormatSignature(card_type_enum, confidence, indicators)

    def get_field_mappings(self, card_type: CardType) -> Optional[dict]:
        """Get field mappings for a specific card type"""
        if card_type.value in self.mappings:
            return self.mappings[card_type.value].get("field_mappings", {})
        return None

    def rules(self) -> Dict:
        """Get detection rules"""
        return self.detection_rules


class StatementOrganizer:
    """Organizes statements by detected format"""

    def __init__(self, output_base: str):
        """Initialize organizer with output directory"""
        self.output_base = output_base
        self.detector = CardFormatDetector()
        self.results = []

    def process_statements(self, input_dirs: List[str]) -> List[Dict]:
        """
        Process all statements from input directories

        Args:
            input_dirs: List of directories containing statements

        Returns:
            List of processing results
        """
        all_files = []

        # Collect all statement files
        for input_dir in input_dirs:
            if os.path.isdir(input_dir):
                for root, dirs, files in os.walk(input_dir):
                    for file in files:
                        if file.endswith(('.csv', '.pdf', '.txt', '.xls', '.xlsx')):
                            all_files.append(os.path.join(root, file))

        # Process each file
        for file_path in all_files:
            result = self._process_file(file_path)
            self.results.append(result)

        return self.results

    def _process_file(self, file_path: str) -> Dict:
        """Process a single statement file"""
        signature = self.detector.detect_format(file_path)
        filename = os.path.basename(file_path)

        # Determine output folder based on card type
        if signature.card_type == CardType.AMEX:
            output_dir = os.path.join(self.output_base, "AmEx_Business")
        elif signature.card_type == CardType.CHASE:
            output_dir = os.path.join(self.output_base, "Chase_Personal")
        elif signature.card_type == CardType.VISA:
            output_dir = os.path.join(self.output_base, "Visa")
        else:
            output_dir = os.path.join(self.output_base, "Unknown")

        os.makedirs(output_dir, exist_ok=True)

        return {
            "file": filename,
            "source_path": file_path,
            "detected_type": signature.card_type.value,
            "confidence": signature.confidence,
            "indicators": signature.indicators,
            "output_dir": output_dir,
            "field_mappings": self.detector.get_field_mappings(signature.card_type)
        }

    def generate_organization_summary(self) -> str:
        """Generate summary of organization results"""
        summary = "CREDIT CARD STATEMENT ORGANIZATION SUMMARY\n"
        summary += "=" * 60 + "\n\n"

        # Group by card type
        by_type = {}
        for result in self.results:
            card_type = result["detected_type"]
            if card_type not in by_type:
                by_type[card_type] = []
            by_type[card_type].append(result)

        # Output by type
        for card_type in [CardType.AMEX.value, CardType.CHASE.value, CardType.VISA.value]:
            if card_type in by_type:
                summary += f"\n{card_type.upper()} STATEMENTS\n"
                summary += "-" * 40 + "\n"
                for result in by_type[card_type]:
                    summary += f"  File: {result['file']}\n"
                    summary += f"  Confidence: {result['confidence']:.1%}\n"
                    summary += f"  Output: {result['output_dir']}\n\n"

        summary += "\nTOTAL PROCESSED: " + str(len(self.results)) + " files\n"
        summary += "\nFOLDER STRUCTURE\n"
        summary += "-" * 40 + "\n"
        summary += "output_directory/\n"
        summary += "  AmEx_Business/\n"
        summary += "  Chase_Personal/\n"
        summary += "  Visa/\n"
        summary += "  Unknown/\n"

        return summary

    def save_results(self, output_file: str):
        """Save processing results to JSON"""
        results_data = {
            "total_processed": len(self.results),
            "by_type": {},
            "details": []
        }

        for result in self.results:
            card_type = result["detected_type"]
            if card_type not in results_data["by_type"]:
                results_data["by_type"][card_type] = 0
            results_data["by_type"][card_type] += 1

            results_data["details"].append({
                "file": result["file"],
                "type": card_type,
                "confidence": result["confidence"],
                "output_directory": result["output_dir"]
            })

        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)


def main():
    """Example usage"""
    print("Credit Card Statement Format Processor")
    print("=" * 60)

    # Configuration
    input_directories = [
        "/Statements/Personal/You/Credit_Cards",
        "/Statements/Business-You/Credit_Cards"
    ]

    output_base = "/Statements/Organized"

    # Initialize and run
    organizer = StatementOrganizer(output_base)

    # Process all statements
    print("\nProcessing statements...")
    results = organizer.process_statements(input_directories)

    # Display results
    for result in results:
        print(f"\nFile: {result['file']}")
        print(f"  Type: {result['detected_type']} (confidence: {result['confidence']:.1%})")
        print(f"  Output: {result['output_dir']}")

    # Generate summary
    summary = organizer.generate_organization_summary()
    print("\n" + summary)

    # Save results
    results_file = os.path.join(output_base, "processing_results.json")
    organizer.save_results(results_file)
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()
