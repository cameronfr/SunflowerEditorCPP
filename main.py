#%%#
import cppyy
import os
import pathlib
import time

editorRuntimeDir = pathlib.Path(__file__).parent.resolve()
llvmDir = "/opt/homebrew/opt/llvm@14"

# import jupyter display
# from IPython.display import display, Javascript, HTML
# from html import escape

import shlex
import ctypes
cppyy.add_include_path(os.path.join(llvmDir, "include"))
cppyy.gbl.gInterpreter.Load(os.path.join(llvmDir, "lib/libLLVM.dylib"))
cppyy.gbl.gInterpreter.Load(os.path.join(llvmDir, "lib/libclang-cpp.dylib"))
cppyy.gbl.gInterpreter.Load(os.path.join(llvmDir, "lib/libclang.dylib"))
cppyy.cppdef("""
  #include "clang-c/Index.h"
  #include "clang-c/Rewrite.h"
""")


globalNsCount = 1
def defineInNewNs(contents):
  global globalNsCount
  globalNsCount += 1
  nsName = f"sfGlobalNs{globalNsCount}"
  cppyy.cppdef(f"""
  namespace {nsName} {{
    {contents}
  }}
  """)
  return (nsName, getattr(cppyy.gbl, nsName))

def includeFile(dir, path, runtimeNsName, transform=False):
  clangNs = cppyy.gbl
  fullPath = os.path.join(dir, path)
  fileContents = open(fullPath, "r").read()
  # Basically want output of cppyy.gbl.gInterpreter.ProcessLine(".I")
  cppyy.gbl.gInterpreter.GetIncludePath()
  clangArgs = shlex.split(cppyy.gbl.gInterpreter.GetIncludePath()) + ["-resource-dir", cppyy.gbl.CppyyLegacy.GetROOT().GetEtcDir().Data() + "cling/lib/clang/9.0.1"]  
  index2 = clangNs.clang_createIndex(0, 0)
  tu2 = clangNs.clang_parseTranslationUnit(index2, fullPath.encode("utf-8"), clangArgs, len(clangArgs), cppyy.nullptr, 0, 0)

  def CXtoCStr(cxstr):
    string = clangNs.clang_getCString(cxstr)
    clangNs.clang_disposeString(cxstr)
    return string

  for i in range(clangNs.clang_getNumDiagnostics(tu2)):
    diag = clangNs.clang_getDiagnostic(tu2, i)
    diagStr = CXtoCStr(clangNs.clang_formatDiagnostic(diag, clangNs.clang_defaultDiagnosticDisplayOptions()))
    diagSeverity = clangNs.clang_getDiagnosticSeverity(diag)
    # print("clang diagnostic: " + diagStr)
    if (diagSeverity > clangNs.CXDiagnostic_Warning):
      print("clang diagnostic: " + diagStr)
      raise Exception("Clang error: ")
    clangNs.clang_disposeDiagnostic(diag)
  
  _, tmp = defineInNewNs("""
    CXCursor* clang_makeCursorCopy(CXCursor* cursor) {
      CXCursor* newCursor = new CXCursor();
      *newCursor = *cursor;
      return newCursor;
    }
  """)
  def getCursorChildren(cursor):
    children = []
    def visit(c, p, l):
      # clang_visitChildren reuses same CXCursor
      cCopy = tmp.clang_makeCursorCopy(c)
      children.append(cCopy)
      return clangNs.CXChildVisit_Continue
    clangNs.clang_visitChildren(cursor, visit, cppyy.nullptr)
    return children
  getCursorChildren(clangNs.clang_getTranslationUnitCursor(tu2))

  cxrewriter = clangNs.clang_CXRewriter_create(tu2)
  def visitor(cursor, depth):
    location = clangNs.clang_getCursorLocation(cursor)
    isFromMainFile = clangNs.clang_Location_isFromMainFile(location)
    if not isFromMainFile:
      return 
    
    clangNs.clang_Location_isFromMainFile
    kind = clangNs.clang_getCursorKind(cursor)
    spelling = CXtoCStr(clangNs.clang_getCursorSpelling(cursor))
    kind = clangNs.clang_getCursorKind(cursor)
    kindReadable = CXtoCStr(clangNs.clang_getCursorKindSpelling(kind))

    line = ctypes.c_uint32()
    column = ctypes.c_uint32()
    clangNs.clang_getExpansionLocation(location, ctypes.c_void_p(), line, column, cppyy.nullptr)
    extent = clangNs.clang_getCursorExtent(cursor)

    # check if it's a printf
    if kind == clangNs.CXCursor_CallExpr:
      if spelling == "printf":
        argStrings = []
        # e.g. printf("hello %d", 5) -> ["printf", "\"hello %d\"", "5"]
        for argCursor in getCursorChildren(cursor):
          argExtent = clangNs.clang_getCursorExtent(argCursor)
          start = clangNs.clang_getRangeStart(argExtent)
          end = clangNs.clang_getRangeEnd(argExtent)
          startIdx = ctypes.c_uint32()
          endIdx = ctypes.c_uint32()
          _file = ctypes.c_void_p()
          clangNs.clang_getExpansionLocation(start, _file, cppyy.nullptr, cppyy.nullptr, startIdx)
          clangNs.clang_getExpansionLocation(end, _file, cppyy.nullptr, cppyy.nullptr, endIdx)
          extentStr = fileContents[startIdx.value:endIdx.value]
          argStrings.append(extentStr) 
          # print("extentStr: " + extentStr)
    
        vaArgs = ", ".join(argStrings[1:])
        truncPath = "/".join(fullPath.split("/")[-3:])
        newCode = f"""
          {{
            int sf_bufferSize = snprintf(NULL, 0, {vaArgs}); 
            char *sf_buffer = (char*)malloc(sf_bufferSize + 1); 
            snprintf(sf_buffer, sf_bufferSize + 1, {vaArgs}); 
            {runtimeNsName}::msgserver_inthread_sendlog("{truncPath}", {line.value-1}, {column.value-1}, sf_buffer); 
            free(sf_buffer); 
          }}
        """
        clangNs.clang_CXRewriter_replaceText(cxrewriter, extent, newCode)
    for child in getCursorChildren(cursor):
      visitor(child, depth+1)

  if transform:
    for child in getCursorChildren(clangNs.clang_getTranslationUnitCursor(tu2)):
      visitor(child, 0)

  cppyy.cppdef("""
    #include "clang/Basic/SourceManager.h"
    #include "clang/Frontend/ASTUnit.h"
    #include "clang/Rewrite/Core/Rewriter.h"
  """)
  _, tmp = defineInNewNs("""
    std::string getRewriteBuffer(CXRewriter rew) {
      clang::Rewriter &rewriter = *(clang::Rewriter*)rew;
      // get the rewritten buffer
      std::string buffer;
      llvm::raw_string_ostream os(buffer);
      rewriter.getEditBuffer(rewriter.getSourceMgr().getMainFileID()).write(os);
      return os.str();
    }
  """)
  transformedFileContents = tmp.getRewriteBuffer(cxrewriter)
  # create jupyter scrollable output
  # display(HTML(f"""
  #   <style>
  #     .sf-code-output {{
  #       max-height: 200px;
  #       overflow-y: scroll;
  #     }}
  #   </style>
  #   <div class="sf-code-output">
  #     <pre>{escape(transformedFileContents)}</pre>
  #   </div>
  # """))
  # print(transformedFileContents)

  return transformedFileContents

cppyy.load_library("libzmq.so")
cppyy.cppdef("""
#include <zmq.h>
#include <math.h>
""")

editorRuntimeNsName, editorRuntime = defineInNewNs(f"""
  {includeFile(editorRuntimeDir, "SunflowerEditorRuntime.cpp", runtimeNsName=None, transform=False)}
""")
editorRuntime.msgserver_init()

#%%# 
_, runtimeTest = defineInNewNs(f"""
  {includeFile(editorRuntimeDir, "SunflowerEditorTesting.cpp", runtimeNsName=editorRuntimeNsName, transform=True)}
""")
runtimeTest.doStuff()
for i in range(100):
  runtimeTest.doStuff2()
  time.sleep(0.05)

#%%#

editorRuntime.msgserver_close()

