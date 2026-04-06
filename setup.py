from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="ai_order_manager",
    version="1.0.0",
    description="AI-powered Order Manager for ERPNext — WhatsApp, Email, Instagram → Sales Order",
    author="Your Company",
    author_email="admin@yourcompany.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
