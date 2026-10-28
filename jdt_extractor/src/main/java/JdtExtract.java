import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import org.eclipse.jdt.core.JavaCore;
import org.eclipse.jdt.core.dom.AST;
import org.eclipse.jdt.core.dom.ASTParser;
import org.eclipse.jdt.core.dom.AbstractTypeDeclaration;
import org.eclipse.jdt.core.dom.Comment;
import org.eclipse.jdt.core.dom.CompilationUnit;
import org.eclipse.jdt.core.dom.EnumDeclaration;
import org.eclipse.jdt.core.dom.TypeDeclaration;

/**
 * Reimplementation of Maldonado's comment extraction/filter pipeline using JDT.
 *
 * Input: repo_map.csv (project,path), files.csv (project,path)
 * Output: project,file,raw,javadoc,license,inner,merge,source,final
 */
public class JdtExtract {
    private static final Pattern JAVADOC_KEEP = Pattern.compile("TODO:|XXX|FIXME");
    private static final Pattern LICENSE = Pattern.compile("copyright", Pattern.CASE_INSENSITIVE);
    private static final Pattern CLASS_BEFORE_KEEP = Pattern.compile("TODO:|XXX|FIXME");
    private static final Pattern SOURCE_CODE = Pattern.compile(
            "else\\s*\\{|"
            + "try\\s*\\{|"
            + "do\\s*\\{|"
            + "finally\\s*\\{|"
            + "if\\s*\\(|"
            + "for\\s*\\(|"
            + "while\\s*\\(|"
            + "switch\\s*\\(|"
            + "Long\\s*\\(|"
            + "Byte\\s*\\(|"
            + "Double\\s*\\(|"
            + "Float\\s*\\(|"
            + "Integer\\s*\\(|"
            + "Short\\s*\\(|"
            + "BigDecimal\\s*\\(|"
            + "BigInteger\\s*\\(|"
            + "Character\\s*\\(|"
            + "Boolean\\s*\\(|"
            + "String\\s*\\(|"
            + "assert\\s*\\(|"
            + "System.out.|"
            + "public\\s*void|"
            + "private\\s*static\\*final|"
            + "catch\\s*\\(");

    enum CommentKind { LINE, BLOCK, JAVADOC }

    static final class C {
        final int startLine;
        int endLine;
        String text;
        CommentKind kind;
        C(int startLine, int endLine, String text, CommentKind kind) {
            this.startLine = startLine;
            this.endLine = endLine;
            this.text = text;
            this.kind = kind;
        }
    }

    static final class Result {
        final int[] counts;
        final List<C> comments;
        Result(int[] counts, List<C> comments) {
            this.counts = counts;
            this.comments = comments;
        }
    }

    static final class TypeInfo {
        final String name;
        final int start;
        final int end;
        final int startLine0;
        final List<C> comments = new ArrayList<>();
        TypeInfo(String name, int start, int end, int startLine0) {
            this.name = name;
            this.start = start;
            this.end = end;
            this.startLine0 = startLine0;
        }
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("usage: JdtExtract repo_map.csv files.csv out.csv [compliance]");
            System.exit(2);
        }
        Path root = Path.of(System.getProperty("user.dir")).toAbsolutePath();
        Map<String, Path> repos = readRepoMap(Path.of(args[0]), root);
        List<String[]> files = readFiles(Path.of(args[1]));
        String compliance = args.length > 3 ? args[3] : "1.8";

        Map<String, Map<String, String>> optionCache = new HashMap<>();

        try (BufferedWriter out = Files.newBufferedWriter(Path.of(args[2]), StandardCharsets.UTF_8);
             BufferedWriter outc = Files.newBufferedWriter(Path.of(args[2] + ".comments.csv"), StandardCharsets.UTF_8)) {
            out.write("project,file,raw,javadoc,license,inner,merge,source,final\n");
            outc.write("project,file,start,end,text_b64\n");
            int done = 0;
            for (String[] row : files) {
                String project = row[0];
                String rel = row[1];
                Path repo = repos.get(project);
                if (repo == null) {
                    System.err.println("no repo for " + project);
                    continue;
                }
                Path file = repo.resolve(rel);
                if (!Files.isRegularFile(file)) {
                    System.err.println("missing " + file);
                    continue;
                }
                String comp = project.startsWith("jEdit") || project.startsWith("apache-ant") ? "1.4" : "1.8";
                Map<String, String> options = optionCache.computeIfAbsent(comp, c -> {
                    Map<String, String> o = JavaCore.getOptions();
                    try {
                        JavaCore.setComplianceOptions(c, o);
                    } catch (RuntimeException e) {
                        JavaCore.setComplianceOptions("1.8", o);
                    }
                    return o;
                });
                Result res = extract(file, comp, options);
                int[] counts = res.counts;
                out.write(csv(project) + "," + csv(rel) + "," + counts[0] + "," + counts[1] + ","
                        + counts[2] + "," + counts[3] + "," + counts[4] + "," + counts[5] + "," + counts[6] + "\n");
                for (C c : res.comments) {
                    outc.write(csv(project) + "," + csv(rel) + "," + c.startLine + "," + c.endLine + ","
                            + Base64.getEncoder().encodeToString(c.text.getBytes(StandardCharsets.UTF_8)) + "\n");
                }
                done++;
                if (done % 500 == 0) {
                    System.err.println("done " + done + "/" + files.size());
                }
            }
        }
    }

    static Result extract(Path file, String compliance, Map<String, String> options) throws IOException {
        String source;
        try {
            source = Files.readString(file, StandardCharsets.UTF_8);
        } catch (java.nio.charset.MalformedInputException e) {
            source = new String(Files.readAllBytes(file), java.nio.charset.Charset.forName("windows-1252"));
        }
        ASTParser parser = ASTParser.newParser(AST.getJLSLatest());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);
        parser.setSource(source.toCharArray());
        parser.setResolveBindings(false);
        parser.setStatementsRecovery(true);
        parser.setBindingsRecovery(false);
        parser.setCompilerOptions(options);
        CompilationUnit unit = (CompilationUnit) parser.createAST(null);

        List<TypeInfo> types = new ArrayList<>();
        for (Object o : unit.types()) {
            AbstractTypeDeclaration d = (AbstractTypeDeclaration) o;
            if (d instanceof TypeDeclaration) {
                TypeDeclaration td = (TypeDeclaration) d;
                types.add(new TypeInfo(td.getName().getIdentifier(), td.getStartPosition(),
                        td.getStartPosition() + td.getLength(),
                        unit.getLineNumber(td.getStartPosition()) - 1));
            } else if (d instanceof EnumDeclaration) {
                EnumDeclaration ed = (EnumDeclaration) d;
                types.add(new TypeInfo(ed.getName().getIdentifier(), ed.getStartPosition(),
                        ed.getStartPosition() + ed.getLength(),
                        unit.getLineNumber(ed.getStartPosition()) - 1));
            }
        }

        String base = file.getFileName().toString();
        int dot = base.lastIndexOf('.');
        if (dot >= 0) base = base.substring(0, dot);

        int raw = 0;
        List<C> comments = new ArrayList<>();
        for (Object o : unit.getCommentList()) {
            Comment c = (Comment) o;
            int start = c.getStartPosition();
            int end = start + c.getLength();
            CommentKind kind = c.isLineComment() ? CommentKind.LINE
                    : c.isDocComment() ? CommentKind.JAVADOC : CommentKind.BLOCK;
            C rec = new C(unit.getLineNumber(start), unit.getLineNumber(end - 1),
                    source.substring(start, end), kind);
            raw++;
            int target = -1;
            for (int i = 0; i < types.size(); i++) {
                TypeInfo t = types.get(i);
                if (t.start <= start && end <= t.end) {
                    target = i;
                    break;
                }
            }
            if (target < 0) {
                for (int i = 0; i < types.size(); i++) {
                    if (types.get(i).name.equals(base)) {
                        target = i;
                        break;
                    }
                }
            }
            if (target >= 0) {
                types.get(target).comments.add(rec);
            }
        }

        // RemoveJavadocComments
        for (TypeInfo t : types) {
            t.comments.removeIf(c -> c.kind == CommentKind.JAVADOC && !JAVADOC_KEEP.matcher(c.text).find());
        }
        int afterJavadoc = count(types);

        // RemoveLicenseComments
        for (TypeInfo t : types) {
            t.comments.removeIf(c -> {
                if (c.endLine > t.startLine0) {
                    return LICENSE.matcher(c.text).find();
                }
                return !CLASS_BEFORE_KEEP.matcher(c.text).find();
            });
        }
        int afterLicense = count(types);

        // RemoveInnerClassesComments: for each file with >1 class, delete classes
        // whose name contains the first class name (inner classes and prefixed siblings).
        if (types.size() > 1) {
            String parent = types.get(0).name;
            for (int i = 1; i < types.size(); i++) {
                if (types.get(i).name.contains(parent)) {
                    types.get(i).comments.clear();
                }
            }
        }
        int afterInner = count(types);

        // MergeMultiLineComments: merge adjacent LINE comments by end line.
        for (TypeInfo t : types) {
            List<C> line = new ArrayList<>();
            for (C c : t.comments) {
                if (c.kind == CommentKind.LINE) line.add(c);
            }
            line.sort(Comparator.comparingInt(c -> c.endLine));
            List<C> merged = new ArrayList<>();
            int i = 0;
            while (i < line.size()) {
                C cur = line.get(i);
                int j = i + 1;
                while (j < line.size() && line.get(j).endLine == line.get(j - 1).endLine + 1) {
                    cur.text = cur.text + " " + line.get(j).text;
                    cur.endLine = line.get(j).endLine;
                    cur.kind = CommentKind.LINE; // MULTLINE behaves like LINE for merging
                    j++;
                }
                merged.add(cur);
                i = j;
            }
            // Replace LINE comments by merged ones; keep block/javadoc.
            t.comments.removeIf(c -> c.kind == CommentKind.LINE);
            t.comments.addAll(merged);
        }
        int afterMerge = count(types);

        // RemoveSourceCodeComments
        for (TypeInfo t : types) {
            t.comments.removeIf(c -> SOURCE_CODE.matcher(c.text).find());
        }
        int afterSource = count(types);

        List<C> commentsOut = new ArrayList<>();
        for (TypeInfo t : types) commentsOut.addAll(t.comments);
        return new Result(new int[] {raw, afterJavadoc, afterLicense, afterInner, afterMerge, afterSource, afterSource}, commentsOut);
    }

    static int count(List<TypeInfo> types) {
        int n = 0;
        for (TypeInfo t : types) n += t.comments.size();
        return n;
    }

    static Map<String, Path> readRepoMap(Path path, Path root) throws IOException {
        Map<String, Path> map = new LinkedHashMap<>();
        try (BufferedReader r = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line = r.readLine();
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] p = line.split(",", -1);
                if (p.length < 2) continue;
                Path repo = Path.of(p[1].trim());
                if (!repo.isAbsolute()) repo = root.resolve(repo);
                map.put(p[0].trim(), repo);
            }
        }
        return map;
    }

    static List<String[]> readFiles(Path path) throws IOException {
        List<String[]> rows = new ArrayList<>();
        try (BufferedReader r = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line = r.readLine();
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] p = line.split(",", -1);
                if (p.length < 2) continue;
                rows.add(new String[] {p[0].trim(), p[1].trim()});
            }
        }
        return rows;
    }

    static String csv(String s) {
        if (s.indexOf(',') >= 0 || s.indexOf('"') >= 0) {
            return "\"" + s.replace("\"", "\"\"") + "\"";
        }
        return s;
    }
}
