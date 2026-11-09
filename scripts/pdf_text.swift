// Write the text of each PDF given to <out>/<name>.txt, with a marker per page.
// Used by read_module_jacks.py on macOS: swift scripts/pdf_text.swift <out> <file.pdf>...
import Foundation
import PDFKit

let out = CommandLine.arguments[1]
for path in CommandLine.arguments.dropFirst(2) {
    let url = URL(fileURLWithPath: path)
    let name = url.deletingPathExtension().lastPathComponent
    guard let doc = PDFDocument(url: url) else {
        print("\(name) unreadable")
        continue
    }
    var text = ""
    for index in 0..<doc.pageCount {
        text += "\n[page \(index + 1)]\n" + (doc.page(at: index)?.string ?? "")
    }
    try text.write(toFile: "\(out)/\(name).txt", atomically: true, encoding: .utf8)
    print("\(name) pages=\(doc.pageCount) chars=\(text.count)")
}
