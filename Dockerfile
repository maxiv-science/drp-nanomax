FROM harbor.maxiv.lu.se/dockerhub/mambaorg/micromamba:1.5.8

COPY --chown=$MAMBA_USER:$MAMBA_USER conda-env.yaml /tmp/env.yaml

RUN micromamba install -y -n base -f /tmp/env.yaml && \
    micromamba clean --all --yes

#RUN micromamba activate
#ENV PATH "$MAMBA_ROOT_PREFIX/bin:$PATH"
ARG MAMBA_DOCKERFILE_ACTIVATE=1

ARG CI_COMMIT_SHA=0000
ARG CI_COMMIT_REF_NAME=none
#ARG CI_COMMIT_AUTHOR=none
#ARG CI_COMMIT_MESSAGE=none
ARG CI_COMMIT_TIMESTAMP=0
ARG CI_PROJECT_URL=none

#WORKDIR /tmp

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip --no-cache-dir install -r /tmp/requirements.txt

COPY src /tmp/src
COPY <<EOF /etc/build_git_meta.json
{
"commit_hash": "${CI_COMMIT_SHA}",
"branch_name": "${CI_COMMIT_REF_NAME}",
"timestamp": "${CI_COMMIT_TIMESTAMP}",
"repository_url": "${CI_PROJECT_URL}"
}
EOF

CMD ["dranspose"]
