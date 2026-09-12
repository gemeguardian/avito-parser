from setuptools import setup, find_packages

setup(
    name="avito-parser",
    version="1.0.0",
    description="Production-grade Avito scraper with automated PoW solver, proxy rotation, and anti-ban mechanisms.",
    author="gemeguardian",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "PySocks>=1.7.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "avito-parser=avito_parser.cli:main",
        ],
    },
    python_requires=">=3.8",
)
