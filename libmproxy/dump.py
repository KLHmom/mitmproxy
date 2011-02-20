import sys, os, traceback
import flow, filt, utils

class DumpError(Exception): pass


class Options(object):
    __slots__ = [
        "kill",
        "request_script",
        "response_script",
        "replay",
        "verbosity",
        "wfile",
    ]
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        for i in self.__slots__:
            if not hasattr(self, i):
                setattr(self, i, None)


class DumpMaster(flow.FlowMaster):
    def __init__(self, server, options, filtstr, outfile=sys.stdout):
        flow.FlowMaster.__init__(self, server, flow.State())
        self.outfile = outfile
        self.o = options

        if filtstr:
            self.filt = filt.parse(filtstr)
        else:
            self.filt = None

        if options.wfile:
            path = os.path.expanduser(options.wfile)
            try:
                f = file(path, "wb")
                self.fwriter = flow.FlowWriter(f)
            except IOError, v:
                raise DumpError(v.strerror)

        if options.replay:
            path = os.path.expanduser(options.replay)
            try:
                f = file(path, "r")
                flows = list(flow.FlowReader(f).stream())
            except IOError, v:
                raise DumpError(v.strerror)
            self.start_playback(flows)

    def _runscript(self, f, script):
        try:
            ret = f.run_script(script)
            if self.o.verbosity > 0:
                print >> self.outfile, ret
        except flow.RunException, e:
            if e.errout:
                eout = "Script output:\n" + self.indent(4, e.errout) + "\n"
            else:
                eout = ""
            raise DumpError(
                    "%s: %s\n%s"%(script, e.args[0], eout)
                )

    def handle_request(self, r):
        f = flow.FlowMaster.handle_request(self, r)
        if self.o.request_script:
            self._runscript(f, self.o.request_script)

        if self.o.replay:
            pb = self.playback(f)
            if not pb:
                if self.o.kill:
                    self.state.kill_flow(f)
                else:
                    r.ack()
        else:
            r.ack()

    def indent(self, n, t):
        l = str(t).strip().split("\n")
        return "\n".join(" "*n + i for i in l)

    def handle_response(self, msg):
        f = flow.FlowMaster.handle_response(self, msg)
        if f:
            if self.o.response_script:
                self._runscript(f, self.o.response_script)
            msg.ack()
            if self.filt and not f.match(self.filt):
                    return
            sz = utils.pretty_size(len(f.response.content))
            if self.o.verbosity == 1:
                print >> self.outfile, f.request.client_conn.address[0],
                print >> self.outfile, f.request.short()
                print >> self.outfile, "  <<",
                print >> self.outfile, f.response.short(), sz
            elif self.o.verbosity == 2:
                print >> self.outfile, f.request.client_conn.address[0],
                print >> self.outfile, f.request.short()
                print >> self.outfile, self.indent(4, f.request.headers)
                print >> self.outfile
                print >> self.outfile, " <<", f.response.short(), sz
                print >> self.outfile, self.indent(4, f.response.headers)
                print >> self.outfile, "\n"
            elif self.o.verbosity == 3:
                print >> self.outfile, f.request.client_conn.address[0],
                print >> self.outfile, f.request.short()
                print >> self.outfile, self.indent(4, f.request.headers)
                if utils.isBin(f.request.content):
                    print >> self.outfile, self.indent(4, utils.hexdump(f.request.content))
                elif f.request.content:
                    print >> self.outfile, self.indent(4, f.request.content)
                print >> self.outfile
                print >> self.outfile, " <<", f.response.short(), sz
                print >> self.outfile, self.indent(4, f.response.headers)
                if utils.isBin(f.response.content):
                    print >> self.outfile, self.indent(4, utils.hexdump(f.response.content))
                elif f.response.content:
                    print >> self.outfile, self.indent(4, f.response.content)
                print >> self.outfile, "\n"
            self.state.delete_flow(f)
            if self.o.wfile:
                self.fwriter.add(f)

# begin nocover
    def run(self):
        try:
            return flow.FlowMaster.run(self)
        except BaseException, v:
            self.shutdown()
            raise
