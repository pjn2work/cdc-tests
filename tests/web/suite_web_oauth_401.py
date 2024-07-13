from testipy.helpers.data_driven_testing import DDTMethods
from testipy.reporter import ReportManager

from toolbox import Toolbox


class SuiteWebOauth401:
    """
    @LEVEL 1
    @TAG DDT WEB 401
    """

    def __init__(self):
        self.ddt = DDTMethods("web_oauth_401.yaml", env_name="", exec_toolbox=Toolbox())

    def test_connectivity(self, ma: dict, rm: ReportManager, **kwargs):
        """
        @LEVEL 2
        @PRIO 0
        """
        self.ddt.run(ma, rm, tag_name="CONNECTIVITY")

    def test_status_code_401(self, ma: dict, rm: ReportManager, **kwargs):
        """
        @ON_SUCCESS 0
        @LEVEL 2
        @PRIO 10
        """
        self.ddt.run(ma, rm, tag_name="TEST_401")
