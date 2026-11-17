"""IT role profiles.

Each family lives in its own module and exposes a ``profiles()`` function. ``PROFILES_BY_ID`` is the lookup the
rest of the app uses, and ``MATCH_ORDER`` controls which profile wins when a job title fits more than one: the
first match wins, so specific titles come before general ones.
"""

from backend.profiles.common import Competency, RoleProfile
from backend.profiles.data import profiles as data_profiles
from backend.profiles.hardware import profiles as hardware_profiles
from backend.profiles.infrastructure import profiles as infrastructure_profiles
from backend.profiles.product import profiles as product_profiles
from backend.profiles.security import profiles as security_profiles
from backend.profiles.software import profiles as software_profiles

PROFILES = (
    software_profiles()
    + data_profiles()
    + infrastructure_profiles()
    + security_profiles()
    + hardware_profiles()
    + product_profiles()
)

PROFILES_BY_ID = {profile.role_id: profile for profile in PROFILES}

# First match wins, so keep specific titles ahead of the general ones that would swallow them.
MATCH_ORDER = (
    # Specific titles whose words also appear in broader profiles.
    "mobile_developer", "game_developer", "qa_engineer",
    "frontend_engineer", "backend_engineer", "fullstack_developer",
    "graduate_software_engineer", "software_engineer_general",
    "machine_learning_engineer", "data_engineer", "analytics_engineer", "data_scientist", "bi_developer", "data_analyst",
    "sre", "cloud_engineer", "devops_cloud_engineer", "network_engineer", "it_support_manager", "it_support",
    "sysadmin", "itsm_consultant",
    "application_security", "penetration_tester", "security_analyst", "grc_analyst", "security_engineer",
    "robotics_graduate", "robotics_engineer", "mechatronics_engineer", "automation_engineer", "embedded_engineer",
    "electronics_engineer",
    "product_manager", "ux_designer", "technical_writer", "solutions_engineer",
    "erp_consultant", "crm_specialist", "business_systems_analyst",
)

assert set(MATCH_ORDER) == set(PROFILES_BY_ID), sorted(set(MATCH_ORDER) ^ set(PROFILES_BY_ID))
