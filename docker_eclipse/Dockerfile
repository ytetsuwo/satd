FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64 \
    ECLIPSE_HOME=/opt/eclipse

RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-8-jdk \
        libgtk2.0-0 \
        libxtst6 \
        libcanberra-gtk-module \
        libglib2.0-0 \
        libx11-xcb1 \
        xvfb \
        xauth \
        postgresql \
        postgresql-client \
        curl \
        ca-certificates \
        unzip \
        procps \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L --fail --max-time 900 \
        -o /tmp/eclipse.tar.gz \
        https://archive.eclipse.org/eclipse/downloads/drops4/R-4.4.2-201502041700/eclipse-SDK-4.4.2-linux-gtk-x86_64.tar.gz \
    && mkdir -p /opt/eclipse \
    && tar xzf /tmp/eclipse.tar.gz -C /opt/eclipse --strip-components=1 \
    && rm /tmp/eclipse.tar.gz

# Prebuilt plugins (sources and patches are in patches/).
COPY jars/gr.uom.java.jdeodorant_5.0.22.jar /opt/eclipse/plugins/
COPY jars/eclipse.commandline_1.0.0.jar /opt/eclipse/plugins/
COPY jars/draw2d-3.8.1-fixed.jar /opt/eclipse/plugins/draw2d-3.8.1.jar

# Register the plugins with Equinox and give the legacy JDT enough heap.
RUN BUNDLES=/opt/eclipse/configuration/org.eclipse.equinox.simpleconfigurator/bundles.info \
    && for line in \
        "gr.uom.java.jdeodorant,5.0.22,file:plugins/gr.uom.java.jdeodorant_5.0.22.jar,4,false" \
        "eclipse.commandline,1.0.0.qualifier,file:plugins/eclipse.commandline_1.0.0.jar,4,false" \
        "org.eclipse.draw2d,3.8.1.201208200205,file:plugins/draw2d-3.8.1.jar,4,false" \
    ; do grep -qxF "$line" "$BUNDLES" || echo "$line" >> "$BUNDLES"; done \
    && sed -i 's/-Xmx512m/-Xmx3072m/' /opt/eclipse/eclipse.ini

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
