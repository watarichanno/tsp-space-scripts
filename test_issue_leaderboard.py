from unittest import mock

import issue_leaderboard


class TestGetPuppetsFromSheet:
    def test_with_existing_values_returns_canonical_name(self):
        row_values = [['Puppet 1', 'Owner 1']]
        execute = mock.Mock(return_value={'values': row_values})
        resource = mock.Mock(get=mock.Mock(return_value=mock.Mock(execute=execute)))

        result = issue_leaderboard.get_puppets_from_sheet(resource, '', '')

        assert result == {'puppet 1': 'owner 1'}

    def test_with_non_existing_values_returns_canonical_name(self):
        execute = mock.Mock(return_value={})
        resource = mock.Mock(get=mock.Mock(return_value=mock.Mock(execute=execute)))

        result = issue_leaderboard.get_puppets_from_sheet(resource, '', '')

        assert result == {}


class TestGetLeaderboard:
    def test_with_puppet_exists_on_start_date(self):
        start_date_issue_counts = {'puppet 1': 1}
        end_date_issue_counts = {'puppet 1': 5}
        puppets = {'puppet 1': 'owner 1'}

        result = issue_leaderboard.get_leaderboard(puppets, start_date_issue_counts,
                                                   end_date_issue_counts)

        assert result == {'owner 1': 4}

    def test_with_puppet_not_exist_on_start_date_but_exists_on_end_date(self):
        start_date_issue_counts = {}
        end_date_issue_counts = {'puppet 1': 5}
        puppets = {'puppet 1': 'owner 1'}

        result = issue_leaderboard.get_leaderboard(puppets, start_date_issue_counts,
                                                   end_date_issue_counts)

        assert result == {'owner 1': 5}

    def test_with_puppet_not_exist_on_start_and_end_date(self):
        start_date_issue_counts = {}
        end_date_issue_counts = {}
        puppets = {'puppet 1': 'owner 1'}

        result = issue_leaderboard.get_leaderboard(puppets, start_date_issue_counts,
                                                   end_date_issue_counts)

        assert result == {'owner 1': 0}

    def test_owner_has_many_puppets(self):
        start_date_issue_counts = {'puppet 1': 0, 'puppet 2': 0}
        end_date_issue_counts = {'puppet 1': 10, 'puppet 2': 5}
        puppets = {'puppet 1': 'owner 1', 'puppet 2': 'owner 1'}

        result = issue_leaderboard.get_leaderboard(puppets, start_date_issue_counts,
                                                   end_date_issue_counts)

        assert result == {'owner 1': 15}

    def test_returns_issue_counts_sorted_in_desc_order(self):
        start_date_issue_counts = {'puppet 1': 0, 'puppet 2': 0}
        end_date_issue_counts = {'puppet 1': 10, 'puppet 2': 5}
        puppets = {'puppet 1': 'owner 1', 'puppet 2': 'owner 2'}

        result = issue_leaderboard.get_leaderboard(puppets, start_date_issue_counts,
                                                   end_date_issue_counts)

        assert result == {'owner 1': 10, 'owner 2': 5}


class TestGetPuppetIssueCounts:
    def test_counts_issues_of_puppet_of_a_member(self, tmp_path):
        xml = """<NATIONS><NATION>
                 <NAME>Puppet 1</NAME>
                 <ISSUES_ANSWERED>5</ISSUES_ANSWERED>
                 </NATION></NATIONS>"""
        xml_path = tmp_path / 'xml_test.xml'
        xml_path.write_text(xml)
        puppets = {'puppet 1': 'owner 1'}

        result = issue_leaderboard.get_puppet_issue_counts(xml_path, puppets)

        assert result == {'puppet 1': 5}

    def test_skips_puppet_not_of_a_member(self, tmp_path):
        xml = """<NATIONS><NATION>
                 <NAME>Puppet 1</NAME>
                 <ISSUES_ANSWERED>5</ISSUES_ANSWERED>
                 </NATION></NATIONS>"""
        xml_path = tmp_path / 'xml_test.xml'
        xml_path.write_text(xml)
        puppets = {}

        result = issue_leaderboard.get_puppet_issue_counts(xml_path, puppets)

        assert result == {}

    def test_counts_issues_of_many_puppets_of_many_members(self, tmp_path):
        xml = """<NATIONS><NATION>
                 <NAME>Puppet 1</NAME>
                 <ISSUES_ANSWERED>1</ISSUES_ANSWERED>
                 </NATION>
                 <NATION>
                 <NAME>Puppet 2</NAME>
                 <ISSUES_ANSWERED>2</ISSUES_ANSWERED>
                 </NATION>
                 <NATION>
                 <NAME>Puppet 3</NAME>
                 <ISSUES_ANSWERED>3</ISSUES_ANSWERED>
                 </NATION></NATIONS>"""

        xml_path = tmp_path / 'xml_test.xml'
        xml_path.write_text(xml)
        puppets = {'puppet 1': 'owner1', 'puppet 2': 'owner 1', 'puppet 3': 'owner 2'}

        result = issue_leaderboard.get_puppet_issue_counts(xml_path, puppets)

        assert result == {'puppet 1': 1, 'puppet 2': 2, 'puppet 3': 3}
