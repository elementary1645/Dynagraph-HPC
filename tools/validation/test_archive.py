"""Diagnostic-specific synthetic transport, profile and evidence adversaries."""
import gzip
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from evidence_archive import create, verify, files, sha
from archive_transport import verify_sidecar
from archive_test_support import fixture


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.e = fixture(self.root)
        self.archive = self.root/'valid.tar.gz'

    def release(self):
        base=self.root/'release';base.mkdir()
        self.source,self.e=fixture(base,release=True)

    def sanitizer(self):
        result=json.loads((self.e/'result.json').read_bytes());result['mode']='sanitize'
        self.write('result.json',result)
        rows=json.loads((self.e/'commands.json').read_bytes())
        next(r for r in rows if r['name']=='configure')['command'] += [
            '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer',
            '-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined']
        next(r for r in rows if r['name']=='ctest')['environment'].update(
            ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
            UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
        self.write('commands.json',rows);self.refresh()

    def configure_data(self,data,change):
        changed=dict(data);name='evidence/commands.json'
        rows=json.loads(changed[name][1]);row=next(r for r in rows if r['name']=='configure')
        change(row)
        self.put(changed,name,rows)
        return changed

    def reject_configure_suffix(self,suffix,diagnostic,sanitizer=False):
        if sanitizer: self.sanitizer()
        data=self.baseline()
        changed=self.configure_data(data,lambda r:r['command'].extend(suffix))
        self.reject(self.pack(changed),diagnostic)

    def write(self,name,value):
        (self.e/name).write_text(json.dumps(value)+'\n')

    def refresh(self):
        self.write('evidence-sha256.json',{n:d['sha256'] for n,d in files(self.e).items()
                                         if '/' not in n and n!='evidence-sha256.json'})

    def baseline(self):
        result=create(self.e,self.source,self.archive)
        self.assertEqual(result['validation_status'],'passed')
        with tarfile.open(self.archive) as tar:
            return {m.name:(m.mode,tar.extractfile(m).read()) for m in tar}

    def put(self,data,name,value):
        data[name]=(data[name][0],json.dumps(value).encode())

    def pack(self,data,refresh=True):
        if refresh:
            for prefix,recursive in [('evidence/pipeline/',True),('evidence/',False)]:
                name=prefix+'evidence-sha256.json'
                if name in data:
                    doc={n[len(prefix):]:hashlib.sha256(raw).hexdigest() for n,(_,raw) in data.items()
                         if n.startswith(prefix) and n!=name and (recursive or '/' not in n[len(prefix):])}
                    self.put(data,name,doc)
            manifest=json.loads(data['archive-manifest.json'][1])
            manifest['files']={n:dict(mode=m,size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                               for n,(m,raw) in data.items() if n!='archive-manifest.json'}
            self.put(data,'archive-manifest.json',manifest)
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w',format=tarfile.PAX_FORMAT) as tar:
            for name,(mode,raw) in data.items():
                info=tarfile.TarInfo(name);info.mode=mode;info.size=len(raw)
                tar.addfile(info,io.BytesIO(raw))
        return gzip.compress(stream.getvalue())

    def reject(self,raw,diagnostic):
        path=self.root/'bad.tar.gz';path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,diagnostic): verify(path)

    def test_roundtrip_modes_and_no_overwrite(self):
        self.baseline()
        with tarfile.open(self.archive) as tar:
            self.assertEqual(tar.getmember('source/run ü.sh').mode,0o755)
        self.assertEqual(verify(self.archive)['passed'],31)
        with self.assertRaisesRegex(ValueError,'outputs must be new'):
            create(self.e,self.source,self.archive)

    def test_valid_release_and_nested_inventory_referenced_cache(self):
        self.release();self.baseline()
        self.assertTrue(verify(self.archive)['smoke'])
        with tarfile.open(self.archive) as tar:
            self.assertEqual(tar.extractfile('evidence/pipeline/mpl-cache/fontlist.json').read(),b'{}')

    def test_missing_member(self):
        data=self.baseline();data.pop('evidence/execution.xml')
        self.reject(self.pack(data),'missing mandatory evidence: execution.xml')

    def test_extra_member(self):
        data=self.baseline();data['evidence/extra']=(0o644,b'extra')
        self.reject(self.pack(data,False),'complete archive inventory/hash/mode mismatch')

    def test_changed_hash(self):
        data=self.baseline();data['evidence/execution.xml']=(0o644,b'changed')
        self.reject(self.pack(data,False),'complete archive inventory/hash/mode mismatch')

    def test_changed_mode(self):
        data=self.baseline();data['source/run ü.sh']=(0o644,data['source/run ü.sh'][1])
        self.reject(self.pack(data,False),'complete archive inventory/hash/mode mismatch')

    def test_source_identity_with_refreshed_outer_hashes(self):
        data=self.baseline();data['source/run ü.sh']=(0o755,b'changed')
        self.reject(self.pack(data),'source inventory mismatch')

    def test_source_file_list_omission_with_refreshed_hashes(self):
        data=self.baseline();data.pop('source/run ü.sh')
        name='evidence/source-identity.json';identity=json.loads(data[name][1]);identity['inventory'].pop('run ü.sh')
        from snapshot import inventory_hash
        identity['inventory_sha256']=inventory_hash(identity['inventory']);self.put(data,name,identity)
        self.reject(self.pack(data),'source file-list inventory mismatch')

    def test_contradictory_revision(self):
        data=self.baseline();name='evidence/source-identity.json';identity=json.loads(data[name][1]);identity['git_revision']='b'*40
        self.put(data,name,identity);self.reject(self.pack(data),'source identity contradicts Git receipts')

    def test_contradictory_mode_and_duplicate_configure_flags(self):
        data=self.baseline();name='evidence/commands.json';rows=json.loads(data[name][1])
        configure=next(r for r in rows if r['name']=='configure')
        configure['command'].append('-DCMAKE_BUILD_TYPE=Release');self.put(data,name,rows)
        self.reject(self.pack(data),'duplicate configure setting: CMAKE_BUILD_TYPE')

    def test_canonical_debug_configure(self):
        self.baseline()
        self.assertEqual(verify(self.archive)['profile'],'debug-full-v1')

    def test_canonical_release_configure(self):
        self.release();self.baseline()
        self.assertEqual(verify(self.archive)['profile'],'release-smoke-v1')

    def test_canonical_sanitizer_configure(self):
        self.sanitizer();self.baseline()
        self.assertEqual(verify(self.archive)['profile'],'sanitize-full-v1')

    def test_split_build_type_override(self):
        self.reject_configure_suffix(['-D','CMAKE_BUILD_TYPE=Release'],'split configure definitions are unsupported')

    def test_split_full_validation_override(self):
        self.reject_configure_suffix(['-D','DYNAGRAPH_FULL_VALIDATION=OFF'],'split configure definitions are unsupported')

    def test_split_sanitizer_compiler_flag_removal(self):
        self.reject_configure_suffix(['-D','CMAKE_CXX_FLAGS='],'split configure definitions are unsupported',sanitizer=True)

    def test_split_sanitizer_linker_flag_removal(self):
        self.reject_configure_suffix(['-D','CMAKE_EXE_LINKER_FLAGS='],'split configure definitions are unsupported',sanitizer=True)

    def test_identical_joined_duplicate(self):
        self.reject_configure_suffix(['-DBUILD_TESTING=ON'],'duplicate configure setting: BUILD_TESTING')

    def test_conflicting_joined_duplicate(self):
        self.reject_configure_suffix(['-DCMAKE_CXX_FLAGS='],'duplicate configure setting: CMAKE_CXX_FLAGS',sanitizer=True)

    def test_missing_split_definition_value(self):
        data=self.baseline()
        for suffix in (['-D'],['-D','-UCMAKE_BUILD_TYPE']):
            changed=self.configure_data(data,lambda r:r['command'].extend(suffix))
            with self.subTest(suffix=suffix): self.reject(self.pack(changed),'missing value after configure -D')

    def test_malformed_definition_tokens(self):
        data=self.baseline()
        for token in ('-DNO_EQUALS','-D=Debug','-DCMAKE_BUILD_TYPE:STRING=Debug','-D CMAKE_BUILD_TYPE=Release'):
            changed=self.configure_data(data,lambda r:r['command'].append(token))
            with self.subTest(token=token): self.reject(self.pack(changed),'unsupported configure definition syntax:')

    def test_unsupported_configure_override_mechanisms(self):
        data=self.baseline()
        cases=[(['-UCMAKE_BUILD_TYPE'],'unsupported configure argument: -UCMAKE_BUILD_TYPE'),
               (['-U','CMAKE_BUILD_TYPE'],'unsupported configure argument: -U'),
               (['-C','/tmp/override.cmake'],'unsupported configure argument: -C'),
               (['--preset=override'],'unsupported configure argument: --preset=override'),
               (['--toolchain=/tmp/override.cmake'],'unsupported configure argument: --toolchain='),
               (['-P','/tmp/override.cmake'],'unsupported configure argument: -P'),
               (['-DCMAKE_TOOLCHAIN_FILE=/tmp/override.cmake'],'unsupported configure setting: CMAKE_TOOLCHAIN_FILE'),
               (['-DCMAKE_PROJECT_TOP_LEVEL_INCLUDES=/tmp/override.cmake'],'unsupported configure setting: CMAKE_PROJECT_TOP_LEVEL_INCLUDES'),
               (['-DCMAKE_USER_MAKE_RULES_OVERRIDE=/tmp/override.cmake'],'unsupported configure setting: CMAKE_USER_MAKE_RULES_OVERRIDE'),
               (['-DCMAKE_CXX_FLAGS_DEBUG='],'unsupported configure setting: CMAKE_CXX_FLAGS_DEBUG')]
        for suffix,diagnostic in cases:
            changed=self.configure_data(data,lambda r:r['command'].extend(suffix))
            with self.subTest(suffix=suffix): self.reject(self.pack(changed),diagnostic)

    def test_empty_or_missing_required_sanitizer_flags(self):
        self.sanitizer();data=self.baseline()
        for key in ('CMAKE_CXX_FLAGS','CMAKE_EXE_LINKER_FLAGS'):
            for missing in (True,False):
                def change(row):
                    row['command']=[a for a in row['command'] if not a.startswith('-D'+key+'=')]
                    if not missing: row['command'].append('-D'+key+'=')
                changed=self.configure_data(data,change)
                diagnostic=('missing canonical configure settings:' if missing else 'validation mode contradicts configure receipt: '+key)
                with self.subTest(key=key,missing=missing): self.reject(self.pack(changed),diagnostic)

    def test_protected_setting_values(self):
        data=self.baseline()
        for key,value in [('CMAKE_BUILD_TYPE','Release'),('DYNAGRAPH_FULL_VALIDATION','OFF'),
                          ('BUILD_TESTING','OFF'),('DYNAGRAPH_WARNINGS_AS_ERRORS','OFF'),('CMAKE_CXX_COMPILER','clang++')]:
            def change(row):
                row['command']=[('-D'+key+'='+value) if a.startswith('-D'+key+'=') else a for a in row['command']]
            changed=self.configure_data(data,change)
            with self.subTest(key=key): self.reject(self.pack(changed),'validation mode contradicts configure receipt: '+key)

    def test_canonical_prefix_paths_and_order(self):
        data=self.baseline()
        def reorder(row): row['command'][7],row['command'][8]=row['command'][8],row['command'][7]
        cases=[(lambda r:r['command'].__setitem__(0,'/usr/bin/cmake'),'noncanonical configure command prefix'),
               (lambda r:r['command'].__setitem__(6,'Ninja'),'noncanonical configure command prefix'),
               (lambda r:r['command'].__setitem__(2,'relative-source'),'invalid canonical configure source/build path'),
               (lambda r:r.__setitem__('cwd','/different/source'),'configure source/cwd mismatch'),
               (lambda r:r['command'].__setitem__(12,'-DDYNAGRAPH_ANALYSIS_PYTHON=relative-python'),'invalid canonical analysis Python path'),
               (reorder,'noncanonical configure definition order')]
        for change,diagnostic in cases:
            changed=self.configure_data(data,change)
            with self.subTest(diagnostic=diagnostic): self.reject(self.pack(changed),diagnostic)

    def test_ordinary_receipt_timestamps(self):
        from archive_contract import receipt_time,MAX_RECEIPT_SECONDS
        for value in (0,0.125,1793284000,1793284000.25,MAX_RECEIPT_SECONDS):
            receipt_time(value,'ordinary','start_unix')
        data=self.baseline();rows=json.loads(data['evidence/commands.json'][1])
        for index,row in enumerate(rows):
            row.update(start_unix=1793284000+2*index+0.25,end_unix=1793284000+2*index+1.25,wall_seconds=1.0)
        self.put(data,'evidence/commands.json',rows)
        path=self.root/'ordinary-time.tar.gz';path.write_bytes(self.pack(data))
        self.assertEqual(verify(path)['passed'],31)

    def test_large_and_out_of_range_receipt_timestamps(self):
        from archive_contract import MAX_RECEIPT_SECONDS
        data=self.baseline()
        for key in ('start_unix','end_unix','wall_seconds'):
            for value in (10**400,MAX_RECEIPT_SECONDS+1,-1):
                changed=dict(data);rows=json.loads(changed['evidence/commands.json'][1]);rows[0][key]=value
                self.put(changed,'evidence/commands.json',rows)
                with self.subTest(key=key,value_kind='huge' if value==10**400 else value):
                    self.reject(self.pack(changed),re.escape('command receipt time out of range: revision.'+key))

    def test_nonfinite_receipt_timestamps(self):
        from archive_contract import receipt_time
        data=self.baseline()
        for value,label in ((float('nan'),'NaN'),(float('inf'),'Infinity'),(float('-inf'),'-Infinity')):
            with self.subTest(value=label):
                with self.assertRaisesRegex(ValueError,'nonfinite command receipt time: nonfinite.start_unix'):
                    receipt_time(value,'nonfinite','start_unix')
                changed=dict(data);rows=json.loads(changed['evidence/commands.json'][1]);rows[0]['start_unix']=value
                self.put(changed,'evidence/commands.json',rows)
                self.reject(self.pack(changed),re.escape('invalid JSON constant: '+label))

    def test_malformed_receipt_timestamp_types(self):
        data=self.baseline()
        for value in ('tomorrow',True,None,{},[]):
            changed=dict(data);rows=json.loads(changed['evidence/commands.json'][1]);rows[0]['start_unix']=value
            self.put(changed,'evidence/commands.json',rows)
            with self.subTest(type=type(value).__name__):
                self.reject(self.pack(changed),'invalid command receipt time type: revision.start_unix')

    def test_controlled_cli_oversized_timestamp(self):
        data=self.baseline();rows=json.loads(data['evidence/commands.json'][1]);rows[0]['start_unix']=10**400
        self.put(data,'evidence/commands.json',rows)
        path=self.root/'huge-time.tar.gz';path.write_bytes(self.pack(data))
        result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('evidence_archive.py')),
                               '--verify',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('Archive rejected: command receipt time out of range: revision.start_unix',result.stderr)
        self.assertNotIn('Traceback',result.stderr)

    def test_profile_mislabeling(self):
        data=self.baseline();m=json.loads(data['archive-manifest.json'][1]);m['profile']='release-smoke-v1'
        self.put(data,'archive-manifest.json',m)
        self.reject(self.pack(data),'validation result/profile mismatch')

    def test_mandatory_result_variants(self):
        data=self.baseline()
        for label,replacement,diagnostic in [
                ('missing',b'<testsuite/>','missing/invalid tests count'),
                ('notrun',data['evidence/execution.xml'][1].replace(b'status="run"',b'status="notrun"',1),'expected executed status run'),
                ('failed',data['evidence/execution.xml'][1].replace(b'<system-out />',b'<failure />',1),'failure/error/skipped'),
                ('skipped',data['evidence/execution.xml'][1].replace(b'<system-out />',b'<skipped />',1),'failure/error/skipped')]:
            changed=dict(data);changed['evidence/execution.xml']=(0o644,replacement)
            with self.subTest(case=label): self.reject(self.pack(changed),diagnostic)

    def test_symlink_and_hardlink_input(self):
        link=self.e/'link';link.symlink_to('execution.xml')
        with self.assertRaisesRegex(ValueError,'unsupported evidence file/link'):
            create(self.e,self.source,self.archive)
        link.unlink();os.link(self.e/'execution.xml',link)
        with self.assertRaisesRegex(ValueError,'unsupported evidence file/link'):
            create(self.e,self.source,self.archive)

    def test_unsafe_duplicate_and_types(self):
        for name,kind,diagnostic in [
                ('../escape',tarfile.REGTYPE,'unsafe archive path'),('/absolute',tarfile.REGTYPE,'unsafe archive path'),
                ('a/../b',tarfile.REGTYPE,'unsafe archive path'),('a//b',tarfile.REGTYPE,'unsafe archive path'),
                ('a\\b',tarfile.REGTYPE,'unsafe archive path'),('C:/drive',tarfile.REGTYPE,'unsafe archive path'),
                ('a',tarfile.SYMTYPE,'unsupported archive member type'),('a',tarfile.LNKTYPE,'unsupported archive member type'),
                ('a',tarfile.FIFOTYPE,'unsupported archive member type'),('a',tarfile.CHRTYPE,'unsupported archive member type'),
                ('a',tarfile.DIRTYPE,'unsupported archive member type'),('a',b'Z','unsupported archive member type'),
                ('duplicate',tarfile.REGTYPE,'duplicate archive member')]:
            raw=io.BytesIO()
            with tarfile.open(fileobj=raw,mode='w') as tar:
                info=tarfile.TarInfo(name);info.type=kind
                if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE): info.linkname='target'
                tar.addfile(info)
                if name=='duplicate': tar.addfile(info)
            with self.subTest(name=name,kind=kind): self.reject(gzip.compress(raw.getvalue()),diagnostic)

    def test_parent_file_collision(self):
        data=self.baseline();data['evidence/a']=(0o644,b'');data['evidence/a/b']=(0o644,b'')
        self.reject(self.pack(data),'file used as archive parent')

    def test_self_consistent_missing_dataset(self):
        self.release();data=self.baseline();data.pop('evidence/pipeline/full-trace/records.jsonl')
        name='evidence/pipeline/pipeline-result.json';doc=json.loads(data[name][1]);doc['dataset_sha256'].pop('full-trace');self.put(data,name,doc)
        self.reject(self.pack(data),'missing mandatory evidence: full-trace/records.jsonl')

    def test_self_consistent_missing_dataset_hash_key(self):
        self.release();data=self.baseline();name='evidence/pipeline/pipeline-result.json'
        doc=json.loads(data[name][1]);doc['dataset_sha256'].pop('full-trace');self.put(data,name,doc)
        self.reject(self.pack(data),'mandatory dataset hash keys mismatch')

    def test_self_consistent_missing_pipeline_receipts(self):
        self.release();data=self.baseline();name='evidence/pipeline/commands.json'
        self.put(data,name,[r for r in json.loads(data[name][1]) if r['name']=='revision'])
        self.reject(self.pack(data),'mandatory stage receipts mismatch')

    def test_self_consistent_missing_environment_policy(self):
        data=self.baseline();data.pop('evidence/environment-policy.json')
        self.reject(self.pack(data),'missing mandatory evidence: environment-policy.json')

    def test_workload_recipe_bounds_before_replay(self):
        self.release();data=self.baseline();name='evidence/pipeline/bundle/manifest.json'
        doc=json.loads(data[name][1]);doc['configuration']['graph']['vertices']=100000
        self.put(data,name,doc)
        self.reject(self.pack(data),'unsupported smoke workload recipe bounds')

    def test_invalid_receipt_schema_has_controlled_diagnostic(self):
        data=self.baseline();name='evidence/commands.json';rows=json.loads(data[name][1]);rows[0].pop('cwd')
        self.put(data,name,rows)
        self.reject(self.pack(data),'incomplete command receipt schema')

    def test_conflicting_failure_marker(self):
        data=self.baseline();data['evidence/failure.json']=(0o644,b'{"status":"failed","error":"SYNTHETIC"}')
        self.reject(self.pack(data),'conflicting failure marker')

    def test_unsuccessful_stage_receipt(self):
        data=self.baseline();name='evidence/commands.json';rows=json.loads(data[name][1]);rows[-1]['exit_code']=1
        self.put(data,name,rows);self.reject(self.pack(data),'unsuccessful stage receipt: source-files-final')

    def test_failed_run_integrity_is_not_validation_success(self):
        (self.e/'result.json').unlink()
        rows=json.loads((self.e/'commands.json').read_bytes())[:4];rows[-1]['exit_code']=1;rows[-1]['error']='SYNTHETIC failure'
        self.write('commands.json',rows);self.write('failure.json',dict(status='failed',classification='command-failed',error='SYNTHETIC failure'))
        self.refresh()
        result=create(self.e,self.source,self.archive,profile='failed-run-v1')
        self.assertEqual(result['status'],'integrity-verified');self.assertEqual(result['validation_status'],'failed');self.assertNotIn('passed',result)
        self.assertEqual(verify(self.archive)['validation_status'],'failed')

    def test_failed_profile_conflicting_success(self):
        self.write('failure.json',dict(status='failed',classification='validation-rejected',error='SYNTHETIC'))
        self.refresh()
        with self.assertRaisesRegex(ValueError,'conflicting success marker'):
            create(self.e,self.source,self.archive,profile='failed-run-v1')

    def test_gzip_footer_and_truncated_stream(self):
        self.baseline();raw=self.archive.read_bytes()
        self.reject(raw[:-8],'incomplete gzip stream/footer')
        self.reject(raw[:len(raw)//2],'incomplete gzip stream/footer')

    def test_gzip_crc_and_size(self):
        self.baseline();raw=self.archive.read_bytes()
        bad=bytearray(raw);bad[-8]^=1;self.reject(bytes(bad),'invalid gzip CRC')
        bad=bytearray(raw);bad[-4]^=1;self.reject(bytes(bad),'invalid gzip size trailer')

    def test_truncated_tar(self):
        self.baseline();raw=gzip.decompress(self.archive.read_bytes())
        self.reject(gzip.compress(raw[:-513]),'truncated tar structure/alignment')
        # Retain member payloads but remove both end markers and record padding.
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tar:
            members=tar.getmembers();last=members[-1];end=last.offset_data+((last.size+511)//512)*512
        self.reject(gzip.compress(raw[:end]),'missing complete tar terminator')

    def test_trailing_compressed_data_and_concatenation(self):
        self.baseline();raw=self.archive.read_bytes()
        self.reject(raw+b'trailing','trailing compressed data or concatenated gzip member')
        self.reject(raw+gzip.compress(b'other stream'),'trailing compressed data or concatenated gzip member')

    def test_trailing_tar_data(self):
        self.baseline();raw=gzip.decompress(self.archive.read_bytes())
        self.reject(gzip.compress(raw+b'x'*512),'unexpected trailing tar data')

    def test_malformed_manifest_root_and_duplicate_keys(self):
        data=self.baseline()
        for value,diagnostic in [(b'[]','invalid JSON evidence root: archive-manifest.json'),
                                 (b'{"files":{},"files":{}}','duplicate JSON key: files')]:
            changed=dict(data);changed['archive-manifest.json']=(0o644,value)
            self.reject(self.pack(changed,False),diagnostic)

    def test_resource_limits(self):
        self.baseline();raw=self.archive.read_bytes()
        for name,value,diagnostic in [('MAX_COMPRESSED',1,'compressed archive size limit'),
                                      ('MAX_EXPANDED',1,'expanded archive size limit'),
                                      ('MAX_FILE',1,'archive member size limit'),
                                      ('MAX_MEMBERS',1,'archive member count limit'),
                                      ('MAX_METADATA',1,'PAX metadata size limit')]:
            with self.subTest(limit=name),patch('archive_transport.'+name,value): self.reject(raw,diagnostic)

    def test_unsupported_pax_field_and_global_header(self):
        for kind,diagnostic in [(tarfile.XHDTYPE,'unsupported or duplicate PAX field'),
                                 (tarfile.XGLTYPE,'unsupported archive member type')]:
            raw=io.BytesIO()
            with tarfile.open(fileobj=raw,mode='w') as tar:
                payload=b'11 size=42\n'  # Deliberately unsupported size override.
                info=tarfile.TarInfo('pax');info.type=kind;info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
                tar.addfile(tarfile.TarInfo('file'))
            self.reject(gzip.compress(raw.getvalue()),diagnostic)

    def test_sha256_sidecar_and_mismatched_pairs(self):
        self.baseline();sidecar=Path(str(self.archive)+'.sha256')
        self.assertEqual(sidecar.read_text(),sha(self.archive)+'  '+self.archive.name+'\n')
        verify_sidecar(self.archive,sidecar)
        result=subprocess.run(['sha256sum','-c',sidecar.name],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        sidecar.write_text('0'*64+'  '+self.archive.name+'\n')
        with self.assertRaisesRegex(ValueError,'sidecar digest mismatch'): verify_sidecar(self.archive,sidecar)
        sidecar.write_text(sha(self.archive)+'  other.tar.gz\n')
        with self.assertRaisesRegex(ValueError,'sidecar archive basename mismatch'): verify_sidecar(self.archive,sidecar)

    def test_unicode_archive_sidecar(self):
        archive=self.root/'evidence ü.tar.gz'
        create(self.e,self.source,archive)
        sidecar=Path(str(archive)+'.sha256')
        verify_sidecar(archive,sidecar)
        result=subprocess.run(['sha256sum','-c',sidecar.name],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_output_parent_alias_cannot_write_source(self):
        alias=self.root/'alias';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'archive output must be outside inputs'):
            create(self.e,self.source,alias/'archive.tar.gz')

    def test_exact_documented_offline_launcher(self):
        from evidence_archive import KIT,kit_path
        self.baseline()
        kit=self.root/'copied kit';kit.mkdir()
        for name in KIT: shutil.copy2(kit_path(name),kit/name)
        launcher='import runpy,sys; kit=sys.argv.pop(1); sys.path.insert(0,kit); runpy.run_path(kit+"/evidence_archive.py",run_name="__main__")'
        command=[sys.executable,'-I','-B','-c',launcher,str(kit),'--verify',str(self.archive),
                 '--sidecar',str(self.archive)+'.sha256']
        result=subprocess.run(command,cwd=kit,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['validation_status'],'passed')

    def test_malformed_tar_checksum(self):
        self.baseline();raw=bytearray(gzip.decompress(self.archive.read_bytes()));raw[0]^=1
        self.reject(gzip.compress(raw),'malformed tar header/checksum')

    def test_controlled_cli_malformed_input(self):
        self.baseline();bad=self.root/'truncated.tar.gz';bad.write_bytes(self.archive.read_bytes()[:100])
        result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('evidence_archive.py')),'--verify',str(bad)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('Archive rejected: incomplete gzip stream/footer',result.stderr)
        self.assertNotIn('Traceback',result.stderr)
        with tarfile.open(self.archive) as tar:
            data={m.name:(m.mode,tar.extractfile(m).read()) for m in tar}
        data['archive-manifest.json']=(0o644,b'[]')
        bad.write_bytes(self.pack(data,False))
        result=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('evidence_archive.py')),'--verify',str(bad)],capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('Archive rejected: invalid JSON evidence root: archive-manifest.json',result.stderr)
        self.assertNotIn('Traceback',result.stderr)


if __name__=='__main__':
    unittest.main(verbosity=2)
