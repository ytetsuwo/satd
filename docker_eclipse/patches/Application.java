package eclipse.commandline;

import gr.uom.java.ast.ASTReader;
import gr.uom.java.ast.ClassObject;
import gr.uom.java.ast.CompilationUnitCache;
import gr.uom.java.ast.MethodObject;
import gr.uom.java.ast.Standalone;
import gr.uom.java.ast.SystemObject;
import gr.uom.java.distance.ExtractClassCandidateGroup;
import gr.uom.java.distance.ExtractClassCandidateRefactoring;
import gr.uom.java.distance.MoveMethodCandidateRefactoring;
import gr.uom.java.jdeodorant.refactoring.manipulators.ASTSlice;
import gr.uom.java.jdeodorant.refactoring.manipulators.ASTSliceGroup;
import gr.uom.java.jdeodorant.refactoring.manipulators.TypeCheckElimination;
import gr.uom.java.jdeodorant.refactoring.manipulators.TypeCheckEliminationGroup;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.ListIterator;
import java.util.Map;
import java.util.Set;

import org.eclipse.core.resources.IFolder;
import org.eclipse.core.resources.IProject;
import org.eclipse.core.resources.IProjectDescription;
import org.eclipse.core.resources.IResource;
import org.eclipse.core.resources.IWorkspace;
import org.eclipse.core.resources.IWorkspaceDescription;
import org.eclipse.core.resources.IWorkspaceRoot;
import org.eclipse.core.resources.IncrementalProjectBuilder;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.core.runtime.CoreException;
import org.eclipse.core.runtime.IPath;
import org.eclipse.core.runtime.Path;
import org.eclipse.equinox.app.IApplication;
import org.eclipse.equinox.app.IApplicationContext;
import org.eclipse.jdt.core.IClasspathEntry;
import org.eclipse.jdt.core.IJavaProject;
import org.eclipse.jdt.core.IPackageFragmentRoot;
import org.eclipse.jdt.core.JavaCore;
import org.eclipse.jdt.ui.PreferenceConstants;

import ca.evermal.comments.CommentAnalyzer;
import ca.evermal.comments.CommentClass;
import ca.evermal.comments.CommentProcessor;
import ca.evermal.comments.CommentExtractor;
import ca.evermal.util.ConnectionFactory;

public class Application implements IApplication {

	private static final int TRUE = 1;

	@Override
	public Object start(IApplicationContext arg0) throws Exception {
		IWorkspace workspace = ResourcesPlugin.getWorkspace();
		IWorkspaceRoot root = workspace.getRoot();
		IPath rootPath = root.getLocation();
		File rootFile = rootPath.toFile();
		File[] contents = rootFile.listFiles();
		IWorkspaceDescription workspaceDescription = workspace.getDescription();
		workspaceDescription.setAutoBuilding(false);
		workspace.setDescription(workspaceDescription);
		importProjects(root);

		//		for(File file : contents) {
		//			if(file.isDirectory() && !file.getName().startsWith(".")) {
		//				String[] dirContents = file.list();
		//				List<String> dirContentsList = Arrays.asList(dirContents);
		//				if(dirContentsList.contains(".project")) {
		//					IProjectDescription description = ResourcesPlugin.getWorkspace().loadProjectDescription(new Path(file.getPath() + "/.project"));
		//					IProject project = ResourcesPlugin.getWorkspace().getRoot().getProject(description.getName());
		//					if(!project.exists()) {
		//						project.create(null);
		//					}
		//					else {
		//						project.refreshLocal(IResource.DEPTH_INFINITE, null);
		//					}
		//					if (!project.isOpen()) {
		//						project.open(null);
		//					}
		//					if(project.hasNature(JavaCore.NATURE_ID)) {
		//						IJavaProject jproject = JavaCore.create(project);
		//						if(!jproject.hasBuildState()) {
		//							project.build(IncrementalProjectBuilder.INCREMENTAL_BUILD, null);
		//							System.out.println("Project " + project.getName() + " built");
		//						}
		//					}
		//				}
		//				else{}
		//				{
		//					boolean builtWithMaven = false;
		//					File[] projectContents = file.listFiles();
		//					for(File content : projectContents) {
		//						if(content.isFile() && content.getName().equals("pom.xml")) {
		//							M2RepoClasspathVariable(rootFile);
		//							builtWithMaven = mvnEclipse(file);
		//							if(builtWithMaven) {
		//								System.out.println("Project " + file.getName() + " built with maven");
		//							}
		//							IProject project = root.getProject(file.getName());
		//							if(!project.exists()) {
		//								project.create(null);
		//							}
		//							else {
		//								project.refreshLocal(IResource.DEPTH_INFINITE, null);
		//							}
		//							if (!project.isOpen()) {
		//								project.open(null);
		//							}
		//							break;
		//						}
		//					}
		//					
		//					if(!builtWithMaven) {
		//						//First create a simple project of type org.eclipse.core.resources.IProject:
		//						IProject project = root.getProject(file.getName());
		//						if(!project.exists()) {
		//							project.create(null);
		//						}
		//						else {
		//							project.refreshLocal(IResource.DEPTH_INFINITE, null);
		//						}
		//						if (!project.isOpen()) {
		//							project.open(null);
		//						}
		//						//you can add in this list more names for source folders
		//						List<String> sourceFolderNames = new ArrayList<String>();
		//						sourceFolderNames.add("src");
		//						sourceFolderNames.add("java");					
		//						List<IResource> sourceFolderResources = new ArrayList<IResource>();
		//						List<IResource> jarFileResources = new ArrayList<IResource>();
		//						for(File content : projectContents) {
		//							if(content.isDirectory()) {
		//								IFolder folder = project.getFolder(content.getName());
		//								jarFileResources.addAll(findFileResources(folder, "jar"));
		//								sourceFolderResources.addAll(findFolderResources(folder, sourceFolderNames));
		//							}
		//						}
		//						//remove the sourceFolders which have child sourceFolders
		//						List<IResource> sourceFoldersToBeRemoved = new ArrayList<IResource>();
		//						for(int i=0; i<sourceFolderResources.size(); i++) {
		//							IResource resourceI = sourceFolderResources.get(i);
		//							IPath pathI = resourceI.getFullPath();
		//							for(int j=i+1; j<sourceFolderResources.size(); j++) {
		//								IResource resourceJ = sourceFolderResources.get(j);
		//								IPath pathJ = resourceJ.getFullPath();
		//								if(pathI.isPrefixOf(pathJ)) {
		//									sourceFoldersToBeRemoved.add(resourceI);
		//								}
		//							}
		//						}
		//						sourceFolderResources.removeAll(sourceFoldersToBeRemoved);
		//						//Because we need a java project, we have to set the Java nature to the created project:
		//						IProjectDescription description = project.getDescription();
		//						description.setNatureIds(new String[] { JavaCore.NATURE_ID });
		//						project.setDescription(description, null);
		//
		//						/*However, it's not enough if we want to add Java source code to the project. We have to set the Java build path:
		//						(1) We first specify the output location of the compiler (the bin folder):*/
		//						IFolder binFolder = project.getFolder("bin");
		//						if(!binFolder.exists()) {
		//							binFolder.create(false, true, null);
		//						}
		//						//Now we can create our Java project
		//						IJavaProject javaProject = JavaCore.create(project);
		//						javaProject.setOutputLocation(binFolder.getFullPath(), null);
		//						
		//						List<IClasspathEntry> libEntries = new ArrayList<IClasspathEntry>();
		//						for(IResource resource : jarFileResources) {
		//							IClasspathEntry libEntry = JavaCore.newLibraryEntry(resource.getFullPath(), null, null, false);
		//							libEntries.add(libEntry);
		//						}
		//						List<IClasspathEntry> sourceEntries = new ArrayList<IClasspathEntry>();
		//						for(IResource resource : sourceFolderResources) {
		//							IPackageFragmentRoot packageFragmentRoot = javaProject.getPackageFragmentRoot(resource);
		//							IClasspathEntry sourceEntry = JavaCore.newSourceEntry(packageFragmentRoot.getPath());
		//							sourceEntries.add(sourceEntry);
		//						}
		//						List<IClasspathEntry> containerEntries = new ArrayList<IClasspathEntry>();
		//						//add JUnit library
		//						Path junitPath = new Path("org.eclipse.jdt.junit.JUNIT_CONTAINER/4");
		//						IClasspathEntry junitEntry = JavaCore.newContainerEntry(junitPath);
		//						containerEntries.add(JavaCore.newContainerEntry(junitEntry.getPath()));
		//
		//						IClasspathEntry[] defaultJRELibraryEntries = PreferenceConstants.getDefaultJRELibrary();
		//						IClasspathEntry[] libEntryArray = libEntries.toArray(new IClasspathEntry[libEntries.size()]);
		//						IClasspathEntry[] sourceEntryArray = sourceEntries.toArray(new IClasspathEntry[sourceEntries.size()]);
		//						IClasspathEntry[] containerEntryArray = containerEntries.toArray(new IClasspathEntry[containerEntries.size()]);
		//
		//						IClasspathEntry[] newEntries = new IClasspathEntry[defaultJRELibraryEntries.length + libEntryArray.length +
		//						                                                   sourceEntryArray.length + containerEntryArray.length];
		//						System.arraycopy(defaultJRELibraryEntries, 0, newEntries, 0, defaultJRELibraryEntries.length);
		//						System.arraycopy(libEntryArray, 0, newEntries, defaultJRELibraryEntries.length, libEntryArray.length);
		//						System.arraycopy(sourceEntryArray, 0, newEntries,
		//								defaultJRELibraryEntries.length + libEntryArray.length, sourceEntryArray.length);
		//						System.arraycopy(containerEntryArray, 0, newEntries,
		//								defaultJRELibraryEntries.length + libEntryArray.length + sourceEntryArray.length, containerEntryArray.length);
		//						javaProject.setRawClasspath(newEntries, null);
		//
		//						if(!javaProject.hasBuildState()) {
		//							project.build(IncrementalProjectBuilder.INCREMENTAL_BUILD, null);
		//							System.out.println("Project " + project.getName() + " built");
		//						}
		//					}
		//				}
		//			}
		//		}
		//
		//		workspace.save(true, null);

		processOpenJavaProjects(root, true, true, false);
//		CommentProcessor processor = new CommentProcessor();
//		processor.execute();
//		processor.executeMergeMultiLines();
		return IApplication.EXIT_OK;
	}

	private void processOpenJavaProjects(IWorkspaceRoot root, boolean commentExtractor, boolean commentProcessor, boolean commentAnalyzer ) throws CoreException {
		IProject[] projects = root.getProjects();
		String onlyProject = System.getProperty("onlyProject");
		for(IProject project : projects) {
			if(onlyProject != null && !onlyProject.isEmpty() && !onlyProject.equals(project.getName())) {
				continue;
			}
			if(project.isOpen()) {
				System.out.println("Running JDeodorant on project " + project.getName());
				if(project.hasNature(JavaCore.NATURE_ID)) {
					SystemObject systemObject = null;
					IJavaProject jproject = null;
					
					if(commentExtractor | commentAnalyzer){
						jproject = JavaCore.create(project);
						CompilationUnitCache.getInstance().clearCache();
					
						if(ASTReader.getSystemObject() != null && project.equals(ASTReader.getExaminedProject())) {
							new ASTReader(jproject, ASTReader.getSystemObject(), null);
						}
						else {
							new ASTReader(jproject, null);
						}

						systemObject = ASTReader.getSystemObject();
					}
										
					if(commentExtractor){
						CommentExtractor.extractFrom(systemObject);
					}
					if(commentProcessor){
						CommentProcessor processor = new CommentProcessor(project.getName());
						processor.execute();
//						processor.matcheExpressionDictionary();
					}
					if(commentAnalyzer){
						ArrayList<CommentClass> commentClassesWithDictionaryMatches = CommentClass.getDictionaryMatchedByProject(project.getName(), ConnectionFactory.getPostgresql());
						int counter = 0;
						for (CommentClass commentClass : commentClassesWithDictionaryMatches) {
							try{
							CommentAnalyzer.start(systemObject, jproject, commentClass);
							commentClass.setAnalyzed(TRUE);
							commentClass.update();
							counter++;
							System.out.println(counter + " out of :" + commentClassesWithDictionaryMatches.size());
							System.gc();
							}
							catch(Exception e){
								System.out.println("*****exception****");
								commentClass.setAnalyzed(TRUE);
								commentClass.update();
								counter++;
							}
						}
//						project.close(null);
					}

					//					break;
					//					List<MoveMethodCandidateRefactoring> moveMethodCandidateList = Standalone.getMoveMethodRefactoringOpportunities(jproject);
					//					System.out.println("Move Method Refactoring Opportunities:");
					//					for(MoveMethodCandidateRefactoring candidate : moveMethodCandidateList) {
					//						System.out.println(candidate);
					//					}
					//
					//					Set<TypeCheckEliminationGroup> typeCheckEliminationGroupList = Standalone.getTypeCheckEliminationRefactoringOpportunities(jproject);
					//					System.out.println("Type Check Elimination Refactoring Opportunities:");
					//					for(TypeCheckEliminationGroup group : typeCheckEliminationGroupList) {
					//						List<TypeCheckElimination> typeCheckEliminationList = group.getCandidates();
					//						for(TypeCheckElimination elimination : typeCheckEliminationList) {
					//							System.out.println(elimination);
					//						}
					//					}
					//
					//					Set<ASTSliceGroup> sliceGroupList = Standalone.getExtractMethodRefactoringOpportunities(jproject);
					//					System.out.println("Extract Method Refactoring Opportunities:");
					//					for(ASTSliceGroup group : sliceGroupList) {
					//						Set<ASTSlice> slices = group.getCandidates();
					//						for(ASTSlice slice : slices) {
					//							System.out.println(slice);
					//						}
					//					}
					//
					//					Set<ExtractClassCandidateGroup> extractClassGroupList = Standalone.getExtractClassRefactoringOpportunities(jproject);
					//					System.out.println("Extract Class Refactoring Opportunities:");
					//					for(ExtractClassCandidateGroup group : extractClassGroupList) {
					//						List<ExtractClassCandidateRefactoring> candidates = group.getCandidates();
					//						for(ExtractClassCandidateRefactoring candidate : candidates) {
					//							System.out.println(candidate);
					//						}
					//					}
				}
			}
		}
		//		CommentProcessor processor = new CommentProcessor();
		//		processor.execute();
	}

	private List<IResource> findFileResources(IFolder resource, String extension) {
		List<IResource> resources = new ArrayList<IResource>();
		try {
			IResource[] members = resource.members();
			for(IResource childResource : members) {
				if(childResource.getType() == IResource.FOLDER) {
					IFolder folder = (IFolder)childResource;
					resources.addAll(findFileResources(folder, extension));
				}
				else if(childResource.getType() == IResource.FILE) {
					String ext = childResource.getFileExtension();
					if(ext != null && ext.equalsIgnoreCase(extension))
						resources.add(childResource);
				}
			}
		} catch (CoreException e) {
			e.printStackTrace();
		}
		return resources;
	}

	private List<IResource> findFolderResources(IFolder resource, List<String> folderNames) {
		List<IResource> resources = new ArrayList<IResource>();
		try {
			if(folderNames.contains(resource.getName())) {
				resources.add(resource);
			}
			IResource[] members = resource.members();
			for(IResource childResource : members) {
				if(childResource.getType() == IResource.FOLDER) {
					IFolder folder = (IFolder)childResource;
					resources.addAll(findFolderResources(folder, folderNames));
				}
			}
		} catch (CoreException e) {
			e.printStackTrace();
		}
		return resources;
	}

	private boolean M2RepoClasspathVariable(File workspace) {
		boolean workspaceConfigured = false;
		try {
			Map<String, String> env = System.getenv();

			ProcessBuilder pb = new ProcessBuilder("cmd.exe", "/c", "mvn", "-Declipse.workspace=.", "eclipse:configure-workspace");
			Map<String, String> environment = pb.environment();
			for(String key : env.keySet()) {
				environment.put(key, env.get(key));
			}
			pb.directory(workspace);
			Process p = pb.start();
			BufferedReader stdInput = new BufferedReader(new InputStreamReader(p.getInputStream()));
			BufferedReader stdError = new BufferedReader(new InputStreamReader(p.getErrorStream()));

			String s = null;
			while ((s = stdInput.readLine()) != null) {
				System.out.println(s);
				if(s.contains("BUILD SUCCESS"))
					workspaceConfigured = true;
			}
			while ((s = stdError.readLine()) != null) {
				System.out.println(s);
			}
		}
		catch(IOException e) {
			e.printStackTrace();
		}
		return workspaceConfigured;
	}

	private boolean mvnEclipse(File directory) {
		boolean successfullyCompiled = false;
		try {
			Map<String, String> env = System.getenv();

			ProcessBuilder pb = new ProcessBuilder("cmd.exe", "/c", "mvn", "eclipse:eclipse");
			Map<String, String> environment = pb.environment();
			for(String key : env.keySet()) {
				environment.put(key, env.get(key));
			}
			pb.directory(directory);
			Process p = pb.start();
			BufferedReader stdInput = new BufferedReader(new InputStreamReader(p.getInputStream()));
			BufferedReader stdError = new BufferedReader(new InputStreamReader(p.getErrorStream()));

			String s = null;
			while ((s = stdInput.readLine()) != null) {
				System.out.println(s);
				if(s.contains("BUILD SUCCESS"))
					successfullyCompiled = true;
			}
			while ((s = stdError.readLine()) != null) {
				System.out.println(s);
			}
		}
		catch(IOException e) {
			e.printStackTrace();
		}
		return successfullyCompiled;
	}

	private void importProjects(IWorkspaceRoot root) throws CoreException {
		File workspaceDir = root.getLocation().toFile();
		File[] dirs = workspaceDir.listFiles();
		if (dirs == null) {
			return;
		}
		for (File dir : dirs) {
			if (!dir.isDirectory() || dir.getName().startsWith(".")) {
				continue;
			}
			String name = dir.getName();
			String onlyProject = System.getProperty("onlyProject");
			if (onlyProject != null && !onlyProject.isEmpty() && !onlyProject.equals(name)) {
				continue;
			}
			try {
			IProject project = root.getProject(name);
			if (project.exists() && project.getFile(".classpath").exists()) {
				System.out.println("Already imported " + name);
				continue;
			}
			if (!project.exists()) {
				IProjectDescription description = ResourcesPlugin.getWorkspace().newProjectDescription(name);
				description.setLocation(new Path(dir.getAbsolutePath()));
				project.create(description, null);
			}
			if (!project.isOpen()) {
				project.open(null);
			}
			IProjectDescription description = project.getDescription();
			description.setNatureIds(new String[] { JavaCore.NATURE_ID });
			project.setDescription(description, null);
			IJavaProject javaProject = JavaCore.create(project);
			IFolder bin = project.getFolder("bin");
			if (!bin.exists()) {
				bin.create(true, true, null);
			}
			javaProject.setOutputLocation(bin.getFullPath(), null);
			List<IClasspathEntry> entries = new ArrayList<IClasspathEntry>();
			entries.add(JavaCore.newContainerEntry(new Path("org.eclipse.jdt.launching.JRE_CONTAINER/org.eclipse.jdt.internal.debug.ui.launcher.StandardVMType/JavaSE-1.8")));
			List<File> sourceRoots = findPackageRoots(dir);
			IPath projectLocation = project.getLocation();
			for (File sourceRoot : sourceRoots) {
				IPath relative = new Path(sourceRoot.getAbsolutePath()).makeRelativeTo(projectLocation);
				IPath sourcePath = (relative.isEmpty() || relative.segmentCount() == 0)
					? project.getFullPath()
					: project.getFullPath().append(relative);
				entries.add(JavaCore.newSourceEntry(sourcePath));
			}
			javaProject.setRawClasspath(entries.toArray(new IClasspathEntry[entries.size()]), null);
			System.out.println("Imported " + name + " sourceRoots=" + sourceRoots.size());
			} catch (Exception e) {
				System.out.println("FAILED to import " + name + ": " + e);
				e.printStackTrace();
			}
		}
	}

	private List<File> findPackageRoots(File projectDir) {
		List<File> javaFiles = new ArrayList<File>();
		collectJavaFiles(projectDir, javaFiles);
		Set<String> roots = new LinkedHashSet<String>();
		for (File javaFile : javaFiles) {
			String packageName = readPackageName(javaFile);
			if (packageName == null || packageName.isEmpty()) {
				continue;
			}
			File root = javaFile.getParentFile();
			String[] parts = packageName.split("\\.");
			for (int i = parts.length - 1; i >= 0; i--) {
				if (root != null && root.getName().equals(parts[i])) {
					root = root.getParentFile();
				} else {
					root = null;
					break;
				}
			}
			if (root != null) {
				roots.add(root.getAbsolutePath());
			}
		}
		List<File> result = new ArrayList<File>();
		for (String root : roots) {
			result.add(new File(root));
		}
		Collections.sort(result, new Comparator<File>() {
			public int compare(File a, File b) {
				return b.getAbsolutePath().length() - a.getAbsolutePath().length();
			}
		});
		List<File> filtered = new ArrayList<File>();
		for (File root : result) {
			boolean covered = false;
			for (File kept : filtered) {
				if (kept.getAbsolutePath().startsWith(root.getAbsolutePath() + File.separator)) {
					covered = true;
					break;
				}
			}
			if (!covered) {
				filtered.add(root);
			}
		}
		List<File> nonNested = new ArrayList<File>();
		for (File root : filtered) {
			boolean ancestor = false;
			for (File other : filtered) {
				if (!other.equals(root) && other.getAbsolutePath().startsWith(root.getAbsolutePath() + File.separator)) {
					ancestor = true;
					break;
				}
			}
			if (!ancestor) {
				nonNested.add(root);
			}
		}
		return nonNested;
	}

	private void collectJavaFiles(File directory, List<File> javaFiles) {
		File[] children = directory.listFiles();
		if (children == null) {
			return;
		}
		for (File child : children) {
			if (child.isDirectory()) {
				String name = child.getName();
				if (name.equals(".git") || name.equals("bin") || name.equals("build") || name.equals("target")) {
					continue;
				}
				collectJavaFiles(child, javaFiles);
			} else if (child.getName().endsWith(".java")) {
				javaFiles.add(child);
			}
		}
	}

	private String readPackageName(File file) {
		BufferedReader reader = null;
		try {
			reader = new BufferedReader(new FileReader(file));
			String line;
			int count = 0;
			while ((line = reader.readLine()) != null && count++ < 200) {
				String trimmed = line.trim();
				if (trimmed.startsWith("package ")) {
					int end = trimmed.indexOf(';');
					if (end > 8) {
						return trimmed.substring(8, end).trim();
					}
				}
			}
		} catch (IOException e) {
			// ignore unreadable files
		} finally {
			if (reader != null) {
				try {
					reader.close();
				} catch (IOException e) {
					// ignore
				}
			}
		}
		return null;
	}

	@Override
	public void stop() {

	}

}
