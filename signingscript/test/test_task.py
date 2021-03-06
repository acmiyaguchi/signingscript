from unittest import TestCase
from scriptworker.exceptions import ScriptWorkerTaskException
from signingscript.task import task_signing_formats, task_cert_type


class TestTaskSigningFormats(TestCase):
    def test_task_signing_formats(self):
        task = {"scopes": ["project:releng:signing:cert:dep",
                           "project:releng:signing:format:mar",
                           "project:releng:signing:format:gpg"]}
        self.assertEqual(["mar", "gpg"], task_signing_formats(task))


class TestTaskCertType(TestCase):
    def test_task_cert_type(self):
        task = {"scopes": ["project:releng:signing:cert:dep",
                           "project:releng:signing:type:mar",
                           "project:releng:signing:type:gpg"]}
        self.assertEqual("project:releng:signing:cert:dep", task_cert_type(task))

    def test_task_cert_type_error(self):
        task = {"scopes": ["project:releng:signing:cert:dep",
                           "project:releng:signing:cert:notdep",
                           "project:releng:signing:type:gpg"]}
        self.assertRaises(ScriptWorkerTaskException, task_cert_type, task)
