from oracle_runtime.control_policy import ControlPolicyReader
def test_control_policy_reader_allows_only_registered_read(tmp_path):
 authority=tmp_path/"authority.yaml"; registry=tmp_path/"repositories.yaml"
 authority.write_text("""policy_version: '0.1'\nmode: deny_by_default\ncapabilities:\n  repository_file_read: {allowed: true, scope: explicitly_registered_repositories}\n  repository_file_write: {allowed: false, requires: explicit_approval_and_scoped_write_permission}\n""")
 registry.write_text("""repositories:\n  - {id: intelligence, full_name: 'AfricaEmperor/alagbara-intelligence'}\n""")
 reader=ControlPolicyReader(authority,registry)
 assert reader.evaluate_repository_read("AfricaEmperor/alagbara-intelligence")["allowed"] is True
 assert reader.evaluate_repository_read("AfricaEmperor/pulse-l1")["allowed"] is False
 assert reader.evaluate_mutation("repository_file_write","AfricaEmperor/alagbara-intelligence")["allowed"] is False
